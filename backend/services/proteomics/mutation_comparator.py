"""
services/proteomics/mutation_comparator.py

مسؤولية هذا الملف: مقارنة تسلسل أحماض المريض الأمينية بالتسلسل المرجعي
السليم (Wild-Type) وإنتاج جدول الطفرات + الإحصائيات.

هذا حساب حتمي بالكامل (Deterministic) - لا علاقة له بأي LLM.
اللي بيدخل هون Python فقط + منطق Pairwise Alignment بسيط.
"""

from typing import List, TypedDict, Literal

MutationType = Literal["Silent", "Missense", "Nonsense", "Frameshift"]


class MutationRow(TypedDict):
    position: int
    reference_aa: str
    patient_aa: str
    mutation_type: MutationType
    predicted_effect: str


class ComparisonResult(TypedDict):
    mutations: List[MutationRow]
    identity_percent: float
    total_mutations: int
    counts_by_type: dict
    confidence_score: float


_EFFECT_DESCRIPTIONS = {
    "Silent": "لا تغيير على مستوى البروتين",
    "Missense": "تغيّر محتمل في الشكل الفراغي للبروتين",
    "Nonsense": "بروتين غير مكتمل / فقدان وظيفي محتمل",
    "Frameshift": "تغيّر جذري في تتابع الأحماض الأمينية بعد نقطة الطفرة",
}


def compare_sequences(
    reference_sequence: str,
    patient_sequence: str,
    confidence_score: float = 100.0,
) -> ComparisonResult:
    """
    يقارن تسلسل المريض بالتسلسل المرجعي موقعاً بموقع (position-by-position)
    ويبني جدول الطفرات والإحصائيات.

    ملاحظة: هذه مقارنة بسيطة بدون Gaps (Insertions/Deletions) - أي أنها
    تفترض المحاذاة بالفعل متساوية الطول أو تُقارن حتى أقصر تسلسل بينهما.
    لدعم Insertions/Deletions الحقيقية يلزم لاحقاً دمج Biopython's
    PairwiseAligner بدل هذه المقارنة المباشرة.

    Args:
        reference_sequence: تسلسل الأحماض الأمينية السليم (Wild-Type).
        patient_sequence: تسلسل الأحماض الأمينية للمريض (ناتج translator.py).
        confidence_score: 100.0 لو المرجع بنية حقيقية موثقة (من sequence_matcher)،
                           أو درجة أقل لو ناتج من نموذج تنبؤي احتياطي (ESMFold).

    Returns:
        ComparisonResult: الجدول + الإحصائيات الكاملة.
    """
    mutations: List[MutationRow] = []
    compare_length = min(len(reference_sequence), len(patient_sequence))

    length_mismatch = len(reference_sequence) != len(patient_sequence)

    for position in range(compare_length):
        ref_aa = reference_sequence[position]
        patient_aa = patient_sequence[position]

        if ref_aa == patient_aa:
            continue  # لا يوجد تغيير بهذا الموقع - لا يُضاف للجدول

        if patient_aa == "*" or patient_aa == "":
            mutation_type: MutationType = "Nonsense"
        else:
            mutation_type = "Missense"

        mutations.append(
            {
                "position": position + 1,  # 1-indexed للعرض البشري
                "reference_aa": ref_aa,
                "patient_aa": patient_aa,
                "mutation_type": mutation_type,
                "predicted_effect": _EFFECT_DESCRIPTIONS[mutation_type],
            }
        )

    # لو الطول مختلف، هذا مؤشر Frameshift/Indel محتمل - نسجله كصف إضافي تنبيهي
    if length_mismatch:
        mutations.append(
            {
                "position": compare_length + 1,
                "reference_aa": (
                    reference_sequence[compare_length]
                    if compare_length < len(reference_sequence)
                    else "-"
                ),
                "patient_aa": (
                    patient_sequence[compare_length]
                    if compare_length < len(patient_sequence)
                    else "-"
                ),
                "mutation_type": "Frameshift",
                "predicted_effect": _EFFECT_DESCRIPTIONS["Frameshift"],
            }
        )

    matches = compare_length - len(
        [m for m in mutations if m["mutation_type"] != "Frameshift"]
    )
    identity_percent = (
        round((matches / compare_length) * 100, 2) if compare_length > 0 else 0.0
    )

    counts_by_type = {
        "Silent": 0,
        "Missense": 0,
        "Nonsense": 0,
        "Frameshift": 0,
    }
    for mutation in mutations:
        counts_by_type[mutation["mutation_type"]] += 1

    return {
        "mutations": mutations,
        "identity_percent": identity_percent,
        "total_mutations": len(mutations),
        "counts_by_type": counts_by_type,
        "confidence_score": confidence_score,
    }