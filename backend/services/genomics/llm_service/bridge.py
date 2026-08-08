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


def _format_codon_row(codon: dict) -> str:
    """
    يبني سطر واحد لكودون متغيّر — كل القيم مأخوذة حرفياً من مخرجات
    mutation_classifier (لا شي مُخترع هون). بيتحمّل اختلاف أسماء الحقول
    البسيطة بين نسخ mutation_classifier المختلفة (fallback بـ .get).
    """
    position = (
        codon.get("codon_number")
        or codon.get("position")
        or codon.get("aa_position")
        or "?"
    )
    dna_before = codon.get("control_codon_dna") or codon.get("control_codon") or "?"
    dna_after = codon.get("patient_codon_dna") or codon.get("patient_codon") or "?"
    mrna_before = codon.get("control_codon_mrna") or dna_before.replace("T", "U")
    mrna_after = codon.get("patient_codon_mrna") or dna_after.replace("T", "U")
    aa_before = codon.get("control_amino_acid") or codon.get("control_aa") or "?"
    aa_after = codon.get("patient_amino_acid") or codon.get("patient_aa") or "?"
    genomic_pos = codon.get("genomic_position") or codon.get("genomic_pos") or ""

    return (
        f"    - Codon #{position}"
        f"{f' (genomic pos {genomic_pos})' if genomic_pos else ''}: "
        f"DNA {dna_before} -> {dna_after} | "
        f"mRNA {mrna_before} -> {mrna_after} | "
        f"Amino acid {aa_before} -> {aa_after}"
    )


def _build_gene_mutations_block(proteins_diff: list) -> str:
    """
    يبني كتلة نصية بصيغة جدول (زي الشكل النموذجي DNA/mRNA/Amino acid)
    لكل جين فيه طفرة فعلية — مباشرة من amino_acid_and_protein_diff
    الحقيقي يلي طالع من الـ pipeline. هاي الكتلة بتنبعت للـ LLM حرفياً
    وبنطلب منه إعادة صياغتها بدون تغيير أي قيمة.
    """
    if not proteins_diff:
        return "No gene-level protein comparison data available."

    lines = []
    for gene in proteins_diff:
        if gene.get("error"):
            lines.append(f"- Gene {gene.get('gene_name', '?')}: analysis error — {gene['error']}")
            continue

        mutation_type = gene.get("mutation_type", "none")
        if mutation_type in (None, "none"):
            continue  # ما فيه طفرة بهاد الجين — منتخطاه، ما منذكره بالتقرير

        gene_name = gene.get("gene_name", "?")
        transcript_id = gene.get("transcript_id", "")
        mutated_codons = gene.get("mutated_codons", []) or gene.get("_patient_codons_full", [])

        lines.append(f"- Gene: {gene_name} (transcript {transcript_id}) — Mutation type: {mutation_type}")
        if not gene.get("is_complete_in_patient_sample", True):
            lines.append("    - NOTE: gene sequence is INCOMPLETE in the patient sample window.")

        if gene.get("mutated_codons"):
            for codon in gene["mutated_codons"]:
                lines.append(_format_codon_row(codon))
        else:
            lines.append("    - (mutation type detected but no per-codon detail available)")

    return "\n".join(lines) if lines else "No mutations detected in any analyzed gene (all sequences match reference)."


def run_llm_report_bridge(output_data_instance) -> str:
    """
    جسر الربط: يأخذ كائن OutputData من جينغو، يسحب البيانات الحقيقية من
    AnalysisReport.source_payload (البروتينات/الجينات/الكودونات المتحورة)
    + إحداثيات 3D، ويغذي سكربت الـ LLM ببرومبت صارم: صياغة فقط، بدون
    اختلاق أي رقم أو اسم جين أو حمض أميني غير موجود بالبيانات.
    """
    input_ref = output_data_instance.input_data
    patient_ref = input_ref.patient

    # 0. البيانات الخام الكاملة (مخزّنة بـ AnalysisReport.source_payload)
    report_obj = getattr(output_data_instance, "report", None)
    source_payload = (report_obj.source_payload if report_obj else None) or {}

    proteins_diff = source_payload.get("amino_acid_and_protein_diff", [])
    genes_info = source_payload.get("genes", [])

    # 1. بيانات المريض الأساسية
    patient_data = {
        'cell_type': input_ref.cell_type.name,
        'chromosome': input_ref.chromosome,
    }

    # 2. بيانات الـ Alignment — الجدول الحقيقي (اسم الجين + الكودونات المتغيّرة)
    affected_proteins = output_data_instance.affected_proteins or {}

    missing_protein_names = [
        name for name, info in affected_proteins.items() if info.get('is_missing')
    ]

    if missing_protein_names:
        disrupted_motifs_summary = (
            f"{len(missing_protein_names)} protein(s) present in the healthy reference "
            f"were not detected in the patient sequence: {', '.join(missing_protein_names)}."
        )
    else:
        disrupted_motifs_summary = "No protein-binding motifs were found missing relative to the reference."

    gene_mutations_block = _build_gene_mutations_block(proteins_diff)

    n_genes_analyzed = len(genes_info)
    n_incomplete = sum(1 for g in genes_info if not g.get("is_complete_in_patient_sample", True))

    alignment_info = {
        'coordinates': f"chr{input_ref.chromosome}:{input_ref.start_pos}-{input_ref.end_pos}",
        'genes_analyzed_count': n_genes_analyzed,
        'incomplete_genes_count': n_incomplete,
        'mutation_details': gene_mutations_block,  # ← الجدول الحقيقي (اسم الجين + الكودونات)
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
        'affected_genes': [g.get("gene_name") for g in proteins_diff if g.get("mutation_type") not in (None, "none")] or "None detected.",
    }

    # 4. لستة البروتينات المفقودة فعلياً
    missing_proteins = missing_protein_names

    logger.info("[LLM Bridge] Triggering LLM report generation for Patient: %s", patient_ref.name)

    # 5. استدعاء دالة توليد التقرير
    report_markdown = generate_clinical_llm_report(
        patient_data=patient_data,
        alignment_info=alignment_info,
        delta_analysis=delta_analysis,
        missing_proteins=missing_proteins,
    )
    return report_markdown