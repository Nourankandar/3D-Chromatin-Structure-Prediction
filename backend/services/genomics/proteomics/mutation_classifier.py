"""
services/genomics/proteomics/mutation_classifier.py
====================================================================
مقارنة تسلسل الأحماض الأمينية (مريض مقابل سليم) وتصنيف نوع الطفرة —
بالاعتماد على خرائط الكودونات الكاملة (من translator.build_codon_map)
حتى نطلع array فيه كل الكودونات المختلفة (مو بس أول واحد).
====================================================================
"""

from typing import List, Optional, TypedDict


class CodonDiff(TypedDict):
    codon_number: int
    reference_codon: str
    patient_codon: str
    reference_amino_acid: str
    patient_amino_acid: str
    genomic_position: int


class MutationResult(TypedDict):
    mutation_type: str            # "none" | "silent" | "missense" | "nonsense" | "frameshift"
    mutated_codons: List[CodonDiff]
    patient_sequence: str
    control_sequence: str


def classify_mutation(
    patient_codons: list,          # List[CodonInfo] من build_codon_map
    control_codons: list,          # List[CodonInfo] من build_codon_map
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
            mutated.append({
                "codon_number": p["codon_number"],
                "reference_codon": c["codon"],
                "patient_codon": p["codon"],
                "reference_amino_acid": c["amino_acid"],
                "patient_amino_acid": p["amino_acid"],
                "genomic_position": p["genomic_position"],
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