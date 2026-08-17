"""
services/genome_reference/fetcher.py
يجيب التسلسل "السليم" (reference) من الجينوم المرجعي بناءً على إحداثيات
معروفة (chromosome, start, end) — بدون تحميل الجينوم كامل بالذاكرة.
يعتمد على pyfaidx (pure Python، بدون حاجة لـ compile) للقراءة العشوائية السريعة
عبر ملف .fai index.
"""

import logging
import os
from pathlib import Path

from pyfaidx import Fasta
from django.conf import settings

logger = logging.getLogger(__name__)


class ReferenceFetchError(Exception):
    """يُرفع عند فشل جلب التسلسل المرجعي."""


def fetch_reference_sequence(chromosome: str, start: int, end: int) -> str:
    """
    يجيب التسلسل السليم (raw string) من الجينوم المرجعي، بنفس الإحداثيات
    يلي انطابق فيها تسلسل المريض — لضمان مقارنة عادلة (نفس الطول والموقع).

    Parameters
    ----------
    chromosome : اسم الكروموسوم متل ما هو مكتوب بالـ FASTA header (مثلاً "1" أو "chr1"
                 حسب مصدر الجينوم يلي حملته — لازم يتطابق تماماً)
    start : بداية 0-based (نفس المخرج من locate_patient_sequence)
    end : نهاية (exclusive)

    Returns
    -------
    str: التسلسل النووي السليم (A/C/G/T/N)

    Raises
    ------
    ReferenceFetchError إذا الكروموسوم مش موجود أو الإحداثيات غير صالحة
    """
    fasta_path = Path(settings.GENOME_REFERENCE_ROOT) / "genome.fa"

    if not fasta_path.exists():
        raise ReferenceFetchError(f"Reference genome not found at {fasta_path}")

    if start < 0 or end <= start:
        raise ReferenceFetchError(f"Invalid coordinates: start={start}, end={end}")

    try:
      
        genome = Fasta(str(fasta_path), rebuild=False)

        if chromosome not in genome.keys():
            alt_name = _try_alternate_chromosome_name(chromosome, list(genome.keys()))
            if alt_name is None:
                available_preview = list(genome.keys())[:5]
                raise ReferenceFetchError(
                    f"Chromosome '{chromosome}' not found in reference. "
                    f"Available: {available_preview}..."
                )
            logger.warning(
                "[Fetcher] Chromosome '%s' not found, using '%s' instead",
                chromosome, alt_name,
            )
            chromosome = alt_name

        chrom_length = len(genome[chromosome])
        if end > chrom_length:
            raise ReferenceFetchError(
                f"End coordinate {end} exceeds chromosome length {chrom_length}"
            )

        # pyfaidx بتستخدم slicing عادي — [start:end] بنفس منطق 0-based, exclusive-end
        sequence = str(genome[chromosome][start:end]).upper()

        genome.close()

        logger.info(
            "[Fetcher] Fetched reference sequence: %s:%s-%s (%d bp)",
            chromosome, start, end, len(sequence),
        )
        return sequence

    except (OSError, ValueError, KeyError) as exc:
        raise ReferenceFetchError(f"Failed to fetch reference sequence: {exc}") from exc


from core.utils.genomics_utils import normalize_chromosome_name

def fetch_reference_sequence_as_fasta_file(
    chromosome: str, start: int, end: int, output_dir: str, record_id: str = "healthy_control"
) -> str:
    sequence = fetch_reference_sequence(chromosome, start, end)
    chromosome_clean = normalize_chromosome_name(chromosome).replace("chr", "", 1)  # يشيل الـ chr إذا موجودة أصلاً

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{record_id}_chr{chromosome_clean}_{start}_{end}.fasta")

    with open(output_path, "w") as f:
        f.write(f">{record_id}|chr{chromosome_clean}:{start}-{end}\n")
        for i in range(0, len(sequence), 60):
            f.write(sequence[i:i + 60] + "\n")

    logger.info("[Fetcher] Saved reference FASTA to: %s", output_path)
    return output_path

def _try_alternate_chromosome_name(chromosome: str, available: list) -> str | None:
    """يحاول يلاقي تسمية بديلة شائعة (1 <-> chr1)."""
    candidates = (
        [f"chr{chromosome}"] if not chromosome.startswith("chr")
        else [chromosome.replace("chr", "", 1)]
    )
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None