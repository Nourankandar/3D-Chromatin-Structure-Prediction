"""
services/genomics/reference/sequence_diff.py
====================================================================
مقارنة مباشرة بين تسلسل المريض والسليم (نفس الإحداثيات تماماً) لتحديد
الفروقات على مستوى النيوكليوتيدات — بدون تنبؤ، بدون موديل، نص مقابل نص.
====================================================================
"""

from dataclasses import dataclass, asdict
from typing import List


@dataclass
class SequenceVariant:
    position: int
    genomic_position: int
    variant_type: str    # "SNP" | "insertion" | "deletion"
    reference_base: str
    patient_base: str


def compare_sequences(patient_seq: str, control_seq: str, genomic_start: int) -> List[SequenceVariant]:
    patient_seq = patient_seq.upper()
    control_seq = control_seq.upper()

    variants: List[SequenceVariant] = []
    min_len = min(len(patient_seq), len(control_seq))

    for i in range(min_len):
        p_base, c_base = patient_seq[i], control_seq[i]
        if p_base != c_base and p_base != "N" and c_base != "N":
            variants.append(SequenceVariant(
                position=i,
                genomic_position=genomic_start + i,
                variant_type="SNP",
                reference_base=c_base,
                patient_base=p_base,
            ))

    if len(patient_seq) > len(control_seq):
        variants.append(SequenceVariant(
            position=min_len,
            genomic_position=genomic_start + min_len,
            variant_type="insertion",
            reference_base="-",
            patient_base=patient_seq[min_len:],
        ))
    elif len(control_seq) > len(patient_seq):
        variants.append(SequenceVariant(
            position=min_len,
            genomic_position=genomic_start + min_len,
            variant_type="deletion",
            reference_base=control_seq[min_len:],
            patient_base="-",
        ))

    return variants


def compare_sequences_as_dict(patient_seq: str, control_seq: str, genomic_start: int) -> List[dict]:
    return [asdict(v) for v in compare_sequences(patient_seq, control_seq, genomic_start)]