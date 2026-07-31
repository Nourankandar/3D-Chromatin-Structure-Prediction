"""
services/proteomics/llm_analyzer.py

مسؤولية هذا الملف: أخذ جدول الطفرات والإحصائيات المحسوبة *مسبقاً وحتمياً*
(من mutation_comparator.py) وصياغة تقرير طبي تفسيري فقط - بدون أي حساب
أو استنتاج رقمي من عند النموذج نفسه.

النموذج المستخدم: meta-llama/Meta-Llama-3.1-8B-Instruct عبر
Hugging Face Inference API (مجاني، ومستقر أكثر من النماذج الطبية
المتخصصة الصغيرة على الـ free tier).

مبدأ التصميم الأهم: الـ Prompt "حازم" (Strict) بحيث يُمنع النموذج من:
- اختراع أرقام أو نسب جديدة غير الموجودة بالجدول.
- تقديم تشخيص قطعي نهائي (لأنه ليس طبيباً ولا بديلاً عن استشارة طبية).
النموذج هنا مفسّر لنتائج جاهزة، وليس مصدر الحقيقة الرقمية.
"""

import os
import requests
from typing import Any, Dict

HUGGINGFACE_API_URL = (
    "https://api-inference.huggingface.co/models/"
    "meta-llama/Meta-Llama-3.1-8B-Instruct"
)

# المفتاح يُقرأ من متغيرات البيئة فقط - لا يوضع هنا مطلقاً (راجعي .env.example)
HF_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")

FALLBACK_REPORT = (
    "### ⚠️ التقرير التفسيري غير متاح حالياً\n"
    "تعذر الاتصال بخدمة التحليل اللغوي (LLM) في الوقت الحالي. "
    "جميع الحسابات الرقمية (نسبة التطابق، جدول الطفرات، التصنيفات) "
    "تمت بنجاح عبر المحرك الحتمي ومتوفرة كاملة في الجداول أعلاه، "
    "وهي لا تعتمد على توفر هذه الخدمة."
)


def _build_medical_prompt(analysis_data: Dict[str, Any]) -> str:
    """
    يبني Prompt حازم (Strict) يمنع الهلوسة: يُعطى النموذج الأرقام
    الجاهزة فقط، ويُطلب منه التفسير النصي حصراً دون تغيير أي رقم.
    """
    protein_name = analysis_data.get("protein_name", "Unknown Protein")
    uniprot_id = analysis_data.get("uniprot_id", "N/A")
    identity_percent = analysis_data.get("identity_percent", 0.0)
    total_mutations = analysis_data.get("total_mutations", 0)
    counts_by_type = analysis_data.get("counts_by_type", {})
    mutations = analysis_data.get("mutations", [])
    confidence_score = analysis_data.get("confidence_score", 0.0)

    mutations_text = "\n".join(
        f"- Position {m['position']}: {m['reference_aa']} -> {m['patient_aa']} "
        f"({m['mutation_type']})"
        for m in mutations[:30]  # حد أقصى لتفادي تضخيم الـ prompt بلا داعٍ
    ) or "No mutations detected (sequences identical)."

    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a molecular biology report-writing assistant. You do NOT calculate
or invent any numbers. You are given pre-computed, verified data below and
your ONLY task is to explain it in clear medical language.

STRICT RULES (must follow exactly):
1. Never invent, modify, recalculate, or contradict any number given below.
2. Never state a definitive clinical diagnosis. Use terms like
   "may suggest", "is consistent with", "warrants further clinical review".
3. If data is insufficient, explicitly say so instead of guessing.
4. Output must be well-structured Markdown with the three sections requested.
5. Do not repeat the raw table; synthesize it into prose.
<|eot_id|><|start_header_id|>user<|end_header_id|>
### Pre-computed Verified Data (do not alter):
- Identified Protein: {protein_name} (UniProt ID: {uniprot_id})
- Sequence Identity to Reference: {identity_percent}%
- Total Mutations Detected: {total_mutations}
- Mutation Type Breakdown: {counts_by_type}
- Confidence Score of Reference Structure: {confidence_score}%
- Mutation Table:
{mutations_text}

### Required Report Sections:
1. **Structural & Functional Impact** — explain plausible effects of these
   specific mutations on folding/stability/function, referencing only the
   data above.
2. **Clinical Significance (Qualitative)** — classify tendency as
   Likely Pathogenic / Likely Benign / Uncertain Significance (VUS),
   with reasoning, while noting this is not a definitive diagnosis.
3. **Biological Summary** — a short paragraph suitable for a report,
   summarizing the above without introducing new numbers.

Respond only in Markdown, in Arabic.
<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    return prompt


def generate_variant_report(analysis_data: Dict[str, Any]) -> str:
    """
    يرسل البيانات المحسوبة مسبقاً لنموذج Llama-3.1-8B-Instruct عبر
    Hugging Face Inference API، ويرجع التقرير التفسيري النهائي.

    Args:
        analysis_data: ناتج mutation_comparator.compare_sequences مع
                       إضافة protein_name/uniprot_id من sequence_matcher.

    Returns:
        نص التقرير بصيغة Markdown، أو FALLBACK_REPORT عند أي فشل
        (شبكة، مفتاح مفقود، أو استجابة غير متوقعة). النظام لا ينهار أبداً
        بسبب فشل هذه الخطوة لأنها تفسيرية فقط، وليست جزءاً من الحسابات.
    """
    if not HF_API_KEY:
        return FALLBACK_REPORT

    prompt = _build_medical_prompt(analysis_data)

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 700,
            "temperature": 0.2,  # منخفضة عمداً لتقليل الهلوسة/الإبداع الزائد
            "top_p": 0.9,
            "return_full_text": False,
        },
    }

    try:
        response = requests.post(
            HUGGINGFACE_API_URL, headers=headers, json=payload, timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and result:
                return result[0].get("generated_text", "").strip() or FALLBACK_REPORT
            if isinstance(result, dict) and "generated_text" in result:
                return result["generated_text"].strip() or FALLBACK_REPORT

        if response.status_code == 503:
            return (
                "⚠️ النموذج قيد التحميل حالياً على سيرفرات Hugging Face "
                "(model cold-start). يرجى إعادة المحاولة خلال ثوانٍ قليلة.\n\n"
                + FALLBACK_REPORT
            )

    except requests.RequestException:
        pass

    return FALLBACK_REPORT