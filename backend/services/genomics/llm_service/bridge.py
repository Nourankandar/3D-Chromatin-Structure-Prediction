# services/llm_service/bridge.py
import json
import logging
import os

from django.conf import settings

from ai_engine.models.LLM_Report.report_generator import generate_clinical_llm_report

logger = logging.getLogger(__name__)


def _load_coords_json(relative_path: str) -> dict | None:
    """يحمّل ملف إحداثيات JSON (لو موجود) عشان ناخذ منه stress/n_points."""
    if not relative_path:
        return None
    absolute_path = os.path.join(settings.MEDIA_ROOT, str(relative_path))
    if not os.path.exists(absolute_path):
        return None
    try:
        with open(absolute_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("[LLM Bridge] Failed to read coords file %s: %s", absolute_path, exc)
        return None


def run_llm_report_bridge(output_data_instance) -> str:
    """
    جسر الربط: يأخذ كائن OutputData من جينغو، يستخرج بياناته الحقيقية
    (بروتينات متأثرة/مفقودة + مقارنة إحداثيات 3D)، ويغذي سكربت الـ LLM.
    """
    input_ref = output_data_instance.input_data
    patient_ref = input_ref.patient

    # 1. بيانات المريض الأساسية
    patient_data = {
        'cell_type': input_ref.cell_type.name,
        'chromosome': input_ref.chromosome,
    }

    # 2. بيانات الـ Alignment — الإحداثيات الحقيقية من InputData
    #    (mutation_details التفصيلية لسا بانتظار diff_patient_vs_reference —
    #    منسجل هيك بوضوح بدل ما نختلق تفاصيل مش موجودة فعلياً)
    affected_proteins = output_data_instance.affected_proteins or {}

    missing_protein_names = [
        name for name, info in affected_proteins.items() if info.get('is_missing')
    ]
    altered_protein_names = [
        name for name, info in affected_proteins.items()
        if not info.get('is_missing') and info.get('delta_score')
    ]

    if missing_protein_names:
        disrupted_motifs_summary = (
            f"{len(missing_protein_names)} protein(s) present in the healthy reference "
            f"were not detected in the patient sequence: {', '.join(missing_protein_names)}."
        )
    else:
        disrupted_motifs_summary = "No protein-binding motifs were found missing relative to the reference."

    alignment_info = {
        'coordinates': f"chr{input_ref.chromosome}:{input_ref.start_pos}-{input_ref.end_pos}",
        'mutation_details': (
            "Base-level mutation diffing against the reference is not yet implemented "
            "(pending diff_patient_vs_reference); this section currently reflects only "
            "the motif-level comparison below."
        ),
        'disrupted_motifs': disrupted_motifs_summary,
    }

    # 3. بيانات الـ Delta — من ملفات إحداثيات 3D الحقيقية (مريض vs سليم)
    patient_coords = _load_coords_json(output_data_instance.coords_patient_file)
    control_coords = _load_coords_json(output_data_instance.coords_control_file)

    if patient_coords and control_coords:
        stress_delta = round(patient_coords['stress'] - control_coords['stress'], 4)
        matrix_difference_summary = (
            f"3D reconstruction stress: patient={patient_coords['stress']}, "
            f"control={control_coords['stress']} (Δ={stress_delta}). "
            f"Higher patient stress relative to control may indicate a less consistent "
            f"chromatin fold at this locus."
        )
    elif patient_coords:
        matrix_difference_summary = (
            f"3D reconstruction available for patient only (stress={patient_coords['stress']}); "
            f"no control structure to compare against yet."
        )
    else:
        matrix_difference_summary = "3D coordinate data not available for comparison."

    delta_analysis = {
        'matrix_difference_summary': matrix_difference_summary,
        'loop_status': "Loop-level insulation scoring is not yet implemented.",
        'affected_genes': altered_protein_names if altered_protein_names else "None detected.",
    }

    # 4. لستة البروتينات المفقودة فعلياً (مش فاضية بعد اليوم)
    missing_proteins = missing_protein_names

    logger.info("[LLM Bridge] Triggering Gemini-2.5-Flash for Patient: %s", patient_ref.name)

    # 5. استدعاء دالة توليد التقرير
    report_markdown = generate_clinical_llm_report(
        patient_data=patient_data,
        alignment_info=alignment_info,
        delta_analysis=delta_analysis,
        missing_proteins=missing_proteins
    )
    return report_markdown