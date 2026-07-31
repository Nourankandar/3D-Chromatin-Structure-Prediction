"""
services/proteomics/pipeline_manager.py

الملف المركزي الذي يربط كل خدمات proteomics ببعضها بترتيب واحد ثابت:

    1. translator.py            → DNA (خام) -> amino_acid_sequence (المريض)
    2. sequence_matcher.py       → إيجاد بروتين مرجعي معروف (أو None)
    3. [Fallback] ESMFold        → لو ما لقينا مطابقة، نتنبأ بالبنية (TODO)
    4. mutation_comparator.py    → مقارنة حتمية: مريض مقابل المرجع السليم
    5. llm_analyzer.py           → تفسير نصي للجدول المحسوب (تكميلي فقط)

مبدأ أساسي: أي فشل بالخطوة 5 (LLM) لا يجب أن يمنع إرجاع بقية النتائج،
لأن الحسابات الرقمية (الخطوات 1-4) مستقلة تماماً عن توفر أي خدمة خارجية.
"""

import logging
from typing import Any, Dict, Optional

from .translator import translate_dna_to_protein
from .sequence_matcher import find_matching_protein
from .mutation_comparator import compare_sequences
from .llm_analyzer import generate_variant_report

logger = logging.getLogger(__name__)


def run_full_analysis(
    patient_dna_sequence: str,
    reference_dna_sequence: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ينفّذ خط الأنابيب الكامل من DNA المريض الخام حتى التقرير النهائي.

    Args:
        patient_dna_sequence: تسلسل DNA خام للمريض (كما ورد من الملف المرفوع).
        reference_dna_sequence: تسلسل DNA مرجعي سليم اختياري، إن أراد المستخدم
            مقارنة صريحة بمرجع محدد بدلاً من الاعتماد فقط على sequence_matcher.
            (مثال استخدام: مقارنة Control مقابل Patient مباشرة).

    Returns:
        قاموس شامل جاهز للـ API response / تخزين بالداتابيز:
        {
            "translation": {...},        # من translator.py
            "protein_match": {...} | None,
            "comparison": {...} | None,   # الجدول + الإحصائيات
            "llm_report": "..." (markdown),
            "warnings": [...]
        }
    """
    warnings: list[str] = []

    # ── الخطوة 1: الترجمة (DNA -> Protein) ──────────────────────────────
    translation_result = translate_dna_to_protein(patient_dna_sequence)
    warnings.extend(translation_result["warnings"])

    patient_protein_sequence = translation_result["amino_acid_sequence"]

    if not patient_protein_sequence:
        # لا فائدة من متابعة الـ pipeline بدون تسلسل بروتين صالح
        warnings.append(
            "تعذر توليد تسلسل بروتين صالح من DNA المريض - "
            "تم إيقاف باقي مراحل التحليل."
        )
        return {
            "translation": translation_result,
            "protein_match": None,
            "comparison": None,
            "llm_report": None,
            "warnings": warnings,
        }

    # ── الخطوة 2: تحديد التسلسل المرجعي (Reference) ─────────────────────
    reference_protein_sequence: Optional[str] = None
    protein_match: Optional[Dict[str, Any]] = None
    confidence_score = 100.0

    if reference_dna_sequence:
        # المستخدم أعطى مرجعاً صريحاً (Control) - نترجمه أيضاً بنفس المحرك
        reference_translation = translate_dna_to_protein(reference_dna_sequence)
        reference_protein_sequence = reference_translation["amino_acid_sequence"]
        warnings.extend(
            f"[Reference] {w}" for w in reference_translation["warnings"]
        )
    else:
        # لا يوجد مرجع صريح -> نبحث عن بروتين معروف يطابق تسلسل المريض
        protein_match = find_matching_protein(patient_protein_sequence)

        if protein_match:
            # وجدنا تطابقاً - لكن هذا يعطينا هوية البروتين فقط، وليس
            # بالضرورة التسلسل المرجعي الكامل بذاته لإجراء المقارنة موضعياً.
            # (ملاحظة تصميم: لمقارنة دقيقة موقع-بموقع، يلزم لاحقاً جلب
            # التسلسل المرجعي الفعلي من UniProt عبر matched_uniprot_id،
            # وهذا TODO منفصل خارج نطاق هذا التمرير).
            logger.info(
                "[Pipeline] تم إيجاد تطابق: %s (%.2f%%)",
                protein_match["matched_protein_name"],
                protein_match["match_identity_percent"],
            )
        else:
            # TODO: تفعيل ESMFold هنا كخيار تنبؤي احتياطي، وخفض confidence_score
            warnings.append(
                "لم يتم إيجاد بروتين مرجعي معروف مطابق - "
                "يلزم تفعيل نموذج التنبؤ الاحتياطي (ESMFold) [غير مُنفّذ بعد]."
            )
            confidence_score = 0.0

    # ── الخطوة 3: المقارنة الحتمية (مريض مقابل مرجع) ────────────────────
    comparison_result = None
    if reference_protein_sequence:
        comparison_result = compare_sequences(
            reference_sequence=reference_protein_sequence,
            patient_sequence=patient_protein_sequence,
            confidence_score=confidence_score,
        )
    else:
        warnings.append(
            "لا يوجد تسلسل مرجعي فعلي لإجراء مقارنة موضعية (Position-by-Position) "
            "- تم الاكتفاء بنتيجة sequence_matcher (إن وجدت) دون جدول طفرات مفصّل."
        )

    # ── الخطوة 4: التقرير التفسيري (LLM) ─────────────────────────────────
    llm_report = None
    if comparison_result:
        llm_input = {
            **comparison_result,
            "protein_name": (
                protein_match["matched_protein_name"] if protein_match else "N/A"
            ),
            "uniprot_id": (
                protein_match["matched_uniprot_id"] if protein_match else "N/A"
            ),
        }
        llm_report = generate_variant_report(llm_input)

    return {
        "translation": translation_result,
        "protein_match": protein_match,
        "comparison": comparison_result,
        "llm_report": llm_report,
        "warnings": warnings,
    }