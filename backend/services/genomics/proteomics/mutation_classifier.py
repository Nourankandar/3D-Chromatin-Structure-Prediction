"""
services/genomics/proteomics/mutation_classifier.py
====================================================================
مقارنة تسلسل الأحماض الأمينية (مريض مقابل سليم) وتصنيف نوع الطفرة —
بالاعتماد على خرائط الكودونات الكاملة (من translator.build_codon_map)
حتى نطلع array فيه كل الكودونات المختلفة (مو بس أول واحد).
====================================================================
"""

from typing import List, Optional, TypedDict

GRANTHAM_TABLE: dict[tuple[str, str], int] = {
    ("A", "R"): 112, ("A", "N"): 111, ("A", "D"): 126, ("A", "C"): 195,
    ("A", "Q"): 91, ("A", "E"): 107, ("A", "G"): 60, ("A", "H"): 86,
    ("A", "I"): 94, ("A", "L"): 96, ("A", "K"): 106, ("A", "M"): 84,
    ("A", "F"): 113, ("A", "P"): 27, ("A", "S"): 99, ("A", "T"): 58,
    ("A", "W"): 148, ("A", "Y"): 112, ("A", "V"): 64,
    ("R", "N"): 86, ("R", "D"): 96, ("R", "C"): 180, ("R", "Q"): 43,
    ("R", "E"): 54, ("R", "G"): 125, ("R", "H"): 29, ("R", "I"): 97,
    ("R", "L"): 102, ("R", "K"): 26, ("R", "M"): 91, ("R", "F"): 97,
    ("R", "P"): 103, ("R", "S"): 110, ("R", "T"): 71, ("R", "W"): 101,
    ("R", "Y"): 77, ("R", "V"): 96,
    ("N", "D"): 23, ("N", "C"): 139, ("N", "Q"): 46, ("N", "E"): 42,
    ("N", "G"): 80, ("N", "H"): 68, ("N", "I"): 149, ("N", "L"): 153,
    ("N", "K"): 94, ("N", "M"): 142, ("N", "F"): 158, ("N", "P"): 91,
    ("N", "S"): 46, ("N", "T"): 65, ("N", "W"): 174, ("N", "Y"): 143,
    ("N", "V"): 133,
    ("D", "C"): 154, ("D", "Q"): 61, ("D", "E"): 45, ("D", "G"): 94,
    ("D", "H"): 81, ("D", "I"): 168, ("D", "L"): 172, ("D", "K"): 101,
    ("D", "M"): 160, ("D", "F"): 177, ("D", "P"): 108, ("D", "S"): 65,
    ("D", "T"): 85, ("D", "W"): 181, ("D", "Y"): 160, ("D", "V"): 152,
    ("C", "Q"): 154, ("C", "E"): 170, ("C", "G"): 159, ("C", "H"): 174,
    ("C", "I"): 198, ("C", "L"): 198, ("C", "K"): 202, ("C", "M"): 196,
    ("C", "F"): 205, ("C", "P"): 169, ("C", "S"): 112, ("C", "T"): 149,
    ("C", "W"): 215, ("C", "Y"): 194, ("C", "V"): 192,
    ("Q", "E"): 29, ("Q", "G"): 87, ("Q", "H"): 24, ("Q", "I"): 109,
    ("Q", "L"): 113, ("Q", "K"): 53, ("Q", "M"): 101, ("Q", "F"): 116,
    ("Q", "P"): 76, ("Q", "S"): 68, ("Q", "T"): 42, ("Q", "W"): 130,
    ("Q", "Y"): 99, ("Q", "V"): 96,
    ("E", "G"): 98, ("E", "H"): 40, ("E", "I"): 134, ("E", "L"): 138,
    ("E", "K"): 56, ("E", "M"): 126, ("E", "F"): 140, ("E", "P"): 93,
    ("E", "S"): 80, ("E", "T"): 65, ("E", "W"): 152, ("E", "Y"): 122,
    ("E", "V"): 121,
    ("G", "H"): 98, ("G", "I"): 135, ("G", "L"): 138, ("G", "K"): 127,
    ("G", "M"): 127, ("G", "F"): 153, ("G", "P"): 42, ("G", "S"): 56,
    ("G", "T"): 59, ("G", "W"): 184, ("G", "Y"): 147, ("G", "V"): 109,
    ("H", "I"): 94, ("H", "L"): 99, ("H", "K"): 32, ("H", "M"): 87,
    ("H", "F"): 100, ("H", "P"): 77, ("H", "S"): 89, ("H", "T"): 47,
    ("H", "W"): 115, ("H", "Y"): 83, ("H", "V"): 84,
    ("I", "L"): 5, ("I", "K"): 102, ("I", "M"): 10, ("I", "F"): 21,
    ("I", "P"): 95, ("I", "S"): 142, ("I", "T"): 89, ("I", "W"): 61,
    ("I", "Y"): 33, ("I", "V"): 29,
    ("L", "K"): 107, ("L", "M"): 15, ("L", "F"): 22, ("L", "P"): 98,
    ("L", "S"): 145, ("L", "T"): 92, ("L", "W"): 61, ("L", "Y"): 36,
    ("L", "V"): 32,
    ("K", "M"): 95, ("K", "F"): 102, ("K", "P"): 103, ("K", "S"): 121,
    ("K", "T"): 78, ("K", "W"): 110, ("K", "Y"): 85, ("K", "V"): 97,
    ("M", "F"): 28, ("M", "P"): 87, ("M", "S"): 135, ("M", "T"): 81,
    ("M", "W"): 67, ("M", "Y"): 36, ("M", "V"): 21,
    ("F", "P"): 114, ("F", "S"): 155, ("F", "T"): 103, ("F", "W"): 40,
    ("F", "Y"): 22, ("F", "V"): 50,
    ("P", "S"): 74, ("P", "T"): 38, ("P", "W"): 147, ("P", "Y"): 110,
    ("P", "V"): 68,
    ("S", "T"): 58, ("S", "W"): 177, ("S", "Y"): 144, ("S", "V"): 124,
    ("T", "W"): 128, ("T", "Y"): 92, ("T", "V"): 69,
    ("W", "Y"): 37, ("W", "V"): 88,
    ("Y", "V"): 55,
}


def _extract_aa_letter(amino_acid_field: str) -> str:
    """
    الحقل amino_acid جاي بصيغة 'Val (V)' من translator.build_codon_map —
    هاي الدالة بتسحب بس الحرف الواحد (V) اللي جوا القوسين.
    لو الصيغة غير متوقعة (حرف واحد مباشرة، مثلاً)، بترجعه كما هو.
    """
    if "(" in amino_acid_field and amino_acid_field.endswith(")"):
        return amino_acid_field.rsplit("(", 1)[1].rstrip(")").strip()
    return amino_acid_field.strip()


def get_grantham_distance(aa1: str, aa2: str) -> Optional[int]:
    """
    يرجع مسافة Grantham بين حمضين أمينيين (0-215) — رقم واحد حتمي من
    جدول ثابت، بدون أي حاجة لبنية ثلاثية الأبعاد أو ملف PDB.
    يرجع None لو أحد الحمضين Stop (*) أو Unknown (X) أو نفس الحمض
    (يعني ما في تغيّر كيميائي أصلاً — بيغطيها classify_mutation عادة
    كـ silent قبل ما توصل لهون، بس منتحقق لأي حالة استدعاء مباشر).
    """
    if aa1 == aa2:
        return 0
    if aa1 in ("*", "X") or aa2 in ("*", "X"):
        return None
    return GRANTHAM_TABLE.get((aa1, aa2)) or GRANTHAM_TABLE.get((aa2, aa1))


def classify_grantham_severity(score: Optional[int]) -> str:
    """
    يصنف شدة الاستبدال الكيميائي بناءً على مسافة Grantham:
      0-50   : conservative (تغيّر بسيط، أحماض أمينية متشابهة كيميائياً)
      51-100 : moderate (تغيّر متوسط)
      101+   : radical (تغيّر جذري — احتمال كبير يأثر على البنية/الوظيفة)
    """
    if score is None:
        return "not_applicable"
    if score <= 50:
        return "conservative"
    if score <= 100:
        return "moderate"
    return "radical"


class CodonDiff(TypedDict):
    codon_number: int
    reference_codon: str
    patient_codon: str
    reference_amino_acid: str
    patient_amino_acid: str
    genomic_position: int
    grantham_distance: Optional[int]
    grantham_severity: str


class MutationResult(TypedDict):
    mutation_type: str            # "none" | "silent" | "missense" | "nonsense" | "frameshift"
    mutated_codons: List[CodonDiff]
    patient_sequence: str
    control_sequence: str


def classify_mutation(
    patient_codons: list,        
    control_codons: list,          
    patient_aa_seq: str,
    control_aa_seq: str,
    patient_cds_len: int,
    control_cds_len: int,
) -> MutationResult:

    # Frameshift: طول الـ CDS نفسه مختلف بمقدار مش من مضاعفات 3
    is_frameshift = (patient_cds_len - control_cds_len) % 3 != 0

    if patient_aa_seq == control_aa_seq and not is_frameshift:
        return {
            "mutation_type": "none",
            "mutated_codons": [],
            "patient_sequence": patient_aa_seq,
            "control_sequence": control_aa_seq,
        }

    min_len = min(len(patient_codons), len(control_codons))
    mutated: List[CodonDiff] = []

    for i in range(min_len):
        p, c = patient_codons[i], control_codons[i]
        if p["codon"] != c["codon"]:
            control_aa_letter = _extract_aa_letter(c["amino_acid"])
            patient_aa_letter = _extract_aa_letter(p["amino_acid"])
            grantham_distance = get_grantham_distance(control_aa_letter, patient_aa_letter)

            mutated.append({
                "codon_number": p["codon_number"],
                "reference_codon": c["codon"],
                "patient_codon": p["codon"],
                "reference_amino_acid": c["amino_acid"],
                "patient_amino_acid": p["amino_acid"],
                "genomic_position": p["genomic_position"],
                "grantham_distance": grantham_distance,
                "grantham_severity": classify_grantham_severity(grantham_distance),
            })

    if is_frameshift:
        mutation_type = "frameshift"
    elif len(patient_aa_seq) != len(control_aa_seq):
        # نونسنس: طول مختلف بدون frameshift بالـ CDS — وقف مبكر
        mutation_type = "nonsense"
    elif not mutated:
        # كودونات تغيّرت لكن نفس الحمض الأميني (redundancy بالشفرة الوراثية) = silent
        mutation_type = "silent" if patient_cds_len == control_cds_len else "none"
    else:
        mutation_type = "missense"

    return {
        "mutation_type": mutation_type,
        "mutated_codons": mutated,
        "patient_sequence": patient_aa_seq,
        "control_sequence": control_aa_seq,
    }