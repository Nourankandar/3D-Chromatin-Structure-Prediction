"""
services/llm_service/report_generator.py
====================================================================
توليد التقرير الطبي عبر LLM مفتوح المصدر من Hugging Face فقط.
حساب واحد، مكتبة واحدة (huggingface_hub) — بدون Groq/Together.

سلسلة fallback بثلاث طبقات:

  1) HF_MODEL_PRIMARY    (افتراضي: deepseek-ai/DeepSeek-V3)
  2) HF_MODEL_FALLBACK   (افتراضي: meta-llama/Llama-3.3-70B-Instruct)
  3) قالب Markdown deterministic — بدون أي LLM، مبني مباشرة من البيانات
     المحسوبة مسبقاً، عشان التقرير ما يضل "فاشل" أبداً.

مبدأ التصميم الثابت: الـ LLM بس بيصيغ بيانات محسوبة مسبقاً — ما بيستنتج
ولا بيخترع أرقام أو حقائق علمية.
====================================================================
"""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# تحميل متغيرات البيئة
# ---------------------------------------------------------------------------
from django.conf import settings

HF_TOKEN = settings.HF_TOKEN
HF_MODEL_PRIMARY = settings.HF_MODEL_PRIMARY
HF_MODEL_FALLBACK = settings.HF_MODEL_FALLBACK

SYSTEM_INSTRUCTION = (
    "You are an expert clinical geneticist and computational biologist. "
    "Your role is to REFORMAT and NARRATE the deterministic genomic analysis "
    "data given to you below into a professional clinical report. "
    "STRICT RULES:\n"
    "1. Every gene name, codon number, DNA triplet, mRNA triplet, amino acid, "
    "and genomic position given to you is FINAL and VERIFIED — copy them "
    "EXACTLY as given. Never change, round, correct, or 'improve' any of these values.\n"
    "2. Never invent a gene, mutation, codon, amino acid, or numeric value that "
    "is not explicitly present in the data below.\n"
    "3. If a section of data says information is unavailable or not yet "
    "implemented, state that plainly — do not fill the gap with guesses.\n"
    "4. Your job is presentation and clinical narrative only, not scientific inference."
)


def _build_user_prompt(patient_data, alignment_info, delta_analysis, missing_proteins) -> str:
    proteins_list_str = ", ".join(missing_proteins) if missing_proteins else "None detected"

    return f"""
=== RECONSTRUCTED GENOMIC CASE DATA ===
- Cell Type Context: {patient_data.get('cell_type')}
- Target Chromosome: {patient_data.get('chromosome')}
- Reference Genome Mapping Coordinates (hg38): {alignment_info.get('coordinates')}
- Genes Analyzed: {alignment_info.get('genes_analyzed_count')}
- Genes Incomplete in Patient Sample: {alignment_info.get('incomplete_genes_count')}

=== VERIFIED GENE-LEVEL MUTATION TABLE (copy values EXACTLY — do not alter) ===
{alignment_info.get('mutation_details')}

=== 3D CHROMATIN ARCHITECTURE (Hi-C INTERACTION DELTA) ===
- Matrix Divergence Summary: {delta_analysis.get('matrix_difference_summary')}
- Chromatin Loop Alteration Status: {delta_analysis.get('loop_status')}
- Downstream Affected Neighboring Genes: {delta_analysis.get('affected_genes')}

=== PROTEIN MOTIF SCANNING & DOCKING ANOMALIES ===
- Disrupted Motif Matches (JASPAR Database): {alignment_info.get('disrupted_motifs')}
- Lost/Displaced Structural Proteins: {proteins_list_str}

=== CLINICAL REPORT REQUIREMENTS ===
Synthesize this data into a rigorous 5-section Markdown clinical report:
1. EXECUTIVE SUMMARY
2. GENE-LEVEL MUTATION FINDINGS — present the verified mutation table above
   clearly (gene name, codon position, DNA/mRNA/amino acid before -> after),
   exactly as given, in a readable Markdown table or list.
3. 3D CHROMATIN IMPACT
4. PROTEIN DOCKING DISRUPTION
5. PATHOGENIC INTERPRETATION & RECOMMENDATIONS
""".strip()


def _call_hf_model(model: str, user_prompt: str) -> str:
    client = InferenceClient(model=model, token=HF_TOKEN)
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2000,
        temperature=0.2,
    )
    text = response.choices[0].message.content
    if not text or not text.strip():
        raise ValueError("Empty response from model")
    return text.strip()


def _deterministic_fallback_report(patient_data, alignment_info, delta_analysis, missing_proteins) -> str:
    """
    قالب نهائي بدون LLM إطلاقاً — بيتفعّل بس لو المودلين (الأساسي
    والاحتياطي) وقعوا. مبني حرفياً من البيانات المحسوبة، بدون أي صياغة
    ذكية، عشان الطبيب يضل عندو تقرير مقروء دايماً.
    """
    proteins_list_str = ", ".join(missing_proteins) if missing_proteins else "None detected"

    return f"""# Clinical Genomic Report (Auto-generated — LLM formatting unavailable)

> ⚠️ Note: Both Hugging Face models were unreachable when this report was
> generated. The content below is a direct, unformatted rendering of the
> deterministic pipeline output — no summarization was applied.

## 1. Executive Summary
Analysis for cell type **{patient_data.get('cell_type')}**, chromosome
**{patient_data.get('chromosome')}**, region **{alignment_info.get('coordinates')}**.

## 2. 3D Chromatin Impact
{delta_analysis.get('matrix_difference_summary')}

Loop status: {delta_analysis.get('loop_status')}

Affected neighboring genes: {delta_analysis.get('affected_genes')}

## 3. Protein Docking Disruption
{alignment_info.get('disrupted_motifs')}

Lost/displaced structural proteins: {proteins_list_str}

## 4. Pathogenic Interpretation
{alignment_info.get('mutation_details')}

## 5. Recommendations
Manual clinical review is recommended given automated narrative generation
was unavailable for this run. Please retry report regeneration once the
Hugging Face endpoint is reachable (see `/reports/<id>/regenerate/`).
"""


def generate_clinical_llm_report(patient_data, alignment_info, delta_analysis, missing_proteins) -> str:
    """
    نقطة الدخول الوحيدة — نفس التوقيع القديم تماماً (bridge.py وtasks.py
    ما بيحتاجوا أي تعديل). بترجع نص Markdown دايماً، حتى لو المودلين
    وقعوا (عبر fallback القالب الأخير).
    """
    if not HF_TOKEN:
        logger.error("[LLM Report] HF_TOKEN missing — using deterministic fallback directly")
        return _deterministic_fallback_report(patient_data, alignment_info, delta_analysis, missing_proteins)

    user_prompt = _build_user_prompt(patient_data, alignment_info, delta_analysis, missing_proteins)

    # 1) المودل الأساسي
    try:
        logger.info("[LLM Report] Trying HF primary model (%s)...", HF_MODEL_PRIMARY)
        return _call_hf_model(HF_MODEL_PRIMARY, user_prompt)
    except Exception as exc:
        logger.warning("[LLM Report] Primary model failed: %s — falling back to %s", exc, HF_MODEL_FALLBACK)

    # 2) المودل الاحتياطي
    try:
        logger.info("[LLM Report] Trying HF fallback model (%s)...", HF_MODEL_FALLBACK)
        return _call_hf_model(HF_MODEL_FALLBACK, user_prompt)
    except Exception as exc:
        logger.warning("[LLM Report] Fallback model failed too: %s — using deterministic template", exc)

    # 3) قالب deterministic نهائي — دايماً بينجح
    logger.error("[LLM Report] Both HF models failed — using deterministic fallback template")
    return _deterministic_fallback_report(patient_data, alignment_info, delta_analysis, missing_proteins)