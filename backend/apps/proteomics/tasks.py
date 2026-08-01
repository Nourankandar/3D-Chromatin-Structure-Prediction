"""
apps/proteomics/tasks.py

مهمة Celery المسؤولة عن تشغيل الـ pipeline كاملاً بالخلفية، وتحديث حالة
ProteinInputData.status خطوة بخطوة حتى يقدر الفرونت إند يعمل polling
عليها بسلاسة (نفس فكرة GenomicPipelineManager الموجودة أصلاً).
"""

import logging
from celery import shared_task
from django.core.files.base import ContentFile

from .models import ProteinInputData, ProteinOutputData
from services.proteomics.pipeline_manager import run_full_analysis
from services.proteomics.structure_fetcher import fetch_structure_as_string
from services.proteomics.esmfold_predictor import predict_structure

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def run_protein_pipeline_task(self, input_data_id: int):
    """
    المهمة الرئيسية: تُستدعى فور رفع تحليل جديد (run-test) أو عند retry.

    ملاحظة على القرار المعماري: نحن لا نمرر أي تسلسل كنص مباشرة لهذه
    المهمة - فقط input_data_id، وكل القراءة/الكتابة على الملفات تتم
    داخل المهمة نفسها. هذا يضمن أن أي retry لاحق يُعيد القراءة من
    القيم المخزنة الحالية بدل الاعتماد على بيانات قديمة بالذاكرة.
    """
    try:
        input_data = ProteinInputData.objects.get(pk=input_data_id)
    except ProteinInputData.DoesNotExist:
        logger.error("[ProteinPipeline] input_data_id=%s غير موجود", input_data_id)
        return

    try:
        _run_pipeline_steps(input_data)
    except Exception:
        logger.exception(
            "[ProteinPipeline] فشل غير متوقع أثناء تحليل input_data_id=%s",
            input_data_id,
        )
        input_data.status = ProteinInputData.Status.FAILED
        input_data.save(update_fields=["status"])


def _run_pipeline_steps(input_data: ProteinInputData) -> None:
    """
    تسلسل الخطوات الفعلي، مفصول عن الـ task نفسها لتسهيل الاختبار
    (unit testing) بدون الحاجة لتشغيل Celery.
    """
    # ── فحص الإلغاء المبكر (لو المستخدم ضغط Stop قبل ما توصل المهمة أصلاً) ──
    input_data.refresh_from_db()
    if input_data.status == ProteinInputData.Status.CANCELLING:
        input_data.status = ProteinInputData.Status.CANCELLED
        input_data.save(update_fields=["status"])
        return

    # ── الخطوة 1: قراءة تسلسل DNA الخام من الملفات المرفوعة ──────────────
    input_data.status = ProteinInputData.Status.TRANSLATING
    input_data.save(update_fields=["status"])

    with input_data.dna_sequence_file.open("r") as f:
        patient_dna_raw = f.read()

    control_dna_raw = None
    if input_data.dna_control_file:
        with input_data.dna_control_file.open("r") as f:
            control_dna_raw = f.read()
    # TODO: لو dna_control_file فاضي، لازم يتولد تلقائياً هون عبر الموديول
    # الموجود أصلاً لجلب/توليد المرجع السليم (المذكور بالمخطط كـ fetcher.py)
    # - لم يتم ربطه بعد لأن التوقيع الفعلي لدالته غير معروف لي حالياً.
    # مثال متوقع:
    #   from services.genomics.reference.fetcher import get_reference_sequence
    #   control_dna_raw = get_reference_sequence(
    #       chromosome=input_data.chromosome,
    #       start=input_data.start_pos,
    #       end=input_data.end_pos,
    #   )

    if _check_cancelled(input_data):
        return

    # ── الخطوة 2: تشغيل الـ pipeline الكامل (ترجمة + مطابقة + مقارنة) ────
    input_data.status = ProteinInputData.Status.MATCHING
    input_data.save(update_fields=["status"])

    analysis_result = run_full_analysis(
        patient_dna_sequence=patient_dna_raw,
        reference_dna_sequence=control_dna_raw,
    )

    if _check_cancelled(input_data):
        return

    # ── الخطوة 3: تجهيز ملف البنية 3D (ESMFold على تسلسل المريض دائماً) ──
    # ملاحظة تصميم مهمة: أي PDB تجريبي من RCSB (لو صار تطابق بالخطوة
    # السابقة) يمثّل فقط البروتين *السليم المرجعي* - لا يعكس إطلاقاً أثر
    # طفرات المريض الفعلية على الشكل الفراغي. لهذا نستخدم ESMFold دائماً
    # على تسلسل المريض نفسه كمصدر البنية المعروضة فعلياً، بغض النظر عن
    # نتيجة sequence_matcher.
    input_data.status = ProteinInputData.Status.PREDICTING_STRUCTURE
    input_data.save(update_fields=["status"])

    protein_match = analysis_result.get("protein_match")
    patient_aa_sequence = analysis_result["translation"]["amino_acid_sequence"]

    prediction = predict_structure(patient_aa_sequence)

    structure_source = ProteinOutputData.StructureSource.ESMFOLD_PREDICTED
    pdb_content = prediction["pdb_content"]
    confidence_score = prediction["confidence_score"]

    if prediction["warnings"]:
        logger.warning(
            "[ProteinPipeline] تحذيرات ESMFold لـ input_data_id=%s: %s",
            input_data.id,
            prediction["warnings"],
        )

    if not prediction["success"]:
        logger.warning(
            "[ProteinPipeline] فشل ESMFold لـ input_data_id=%s - "
            "سيُحفظ السجل بدون ملف بنية متنبأة.",
            input_data.id,
        )

    if _check_cancelled(input_data):
        return

    # ── الخطوة 4: حفظ النتائج النهائية ────────────────────────────────────
    translation = analysis_result["translation"]
    comparison = analysis_result.get("comparison") or {}

    output_data = ProteinOutputData(
        input_data=input_data,
        patient_aa_sequence=translation["amino_acid_sequence"],
        control_aa_sequence="",  # TODO: تعبأ من reference_translation عند ربط fetcher.py
        matched_protein_name=(
            protein_match["matched_protein_name"] if protein_match else None
        ),
        matched_uniprot_id=(
            protein_match["matched_uniprot_id"] if protein_match else None
        ),
        matched_pdb_id=protein_match["matched_pdb_id"] if protein_match else None,
        match_identity_percent=(
            protein_match["match_identity_percent"] if protein_match else None
        ),
        structure_source=structure_source,
        confidence_score=confidence_score,
        amino_acid_comparison=comparison.get("mutations", []),
        mutation_summary={
            "identity_percent": comparison.get("identity_percent"),
            "total_mutations": comparison.get("total_mutations"),
            "counts_by_type": comparison.get("counts_by_type"),
            "llm_report": analysis_result.get("llm_report"),
            # دمج تحذيرات الـ pipeline العامة مع تحذيرات ESMFold تحديداً،
            # حتى توصل كل رسائل الفشل/التنبيه للفرونت إند وليس فقط للـ logs.
            "warnings": analysis_result.get("warnings", []) + prediction["warnings"],
        },
    )

    if pdb_content:
        # اسم فريد مرتبط بالـ input_data.id (بدل اسم ثابت "structure.pdb")
        # لتفادي أي تضارب أسماء ملفات بين تحليلات مختلفة، خصوصاً أن
        # المصدر الآن هو ESMFold دائماً وليس PDB ID مميز من RCSB.
        filename = f"esmfold_patient_{input_data.id}.pdb"
        output_data.structure_file.save(
            filename, ContentFile(pdb_content), save=False
        )

    output_data.save()

    input_data.status = ProteinInputData.Status.COMPLETED
    input_data.save(update_fields=["status"])


def _check_cancelled(input_data: ProteinInputData) -> bool:
    """
    يتحقق من حالة الإلغاء بين كل خطوة وأخرى، ويحدّث الحالة النهائية
    لو المستخدم كان طلب Stop أثناء التنفيذ.
    """
    input_data.refresh_from_db()
    if input_data.status == ProteinInputData.Status.CANCELLING:
        input_data.status = ProteinInputData.Status.CANCELLED
        input_data.save(update_fields=["status"])
        return True
    return False