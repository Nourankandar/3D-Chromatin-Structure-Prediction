"""
services/proteomics/splicer.py
====================================================================
يحوّل تسلسل DNA جينومي خام (فيه إكسونات وانترونات) إلى تسلسل الـ CDS
الناضج (Coding Sequence فقط، بدون UTR وبدون انترونات) — جاهز للترجمة
المباشرة عبر translator.py من أول حرف مباشرة، بدون أي بحث عن ATG،
لأنه بداية الترجمة هون مضمونة 100% من الـ GTF نفسه.

المنطق:
  1) لكل إكسون، نقص فقط الجزء المتقاطع مع حدود الـ CDS (أول/آخر إكسون
     غالباً فيهم UTR غير مرمز لازم يتقص).
  2) لو strand == "-": نعمل reverse complement لكل قطعة *لحالها*،
     وبعدين نلزقهم بترتيب معكوس — لأنه عالخيط السالب، آخر إكسون
     جينومياً هو أول إكسون فعلياً بالـ mRNA المُترجم.
  3) لو strand == "+": نلزق القطع بترتيبها الجينومي العادي مباشرة.
====================================================================
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


class SplicingError(Exception):
    """يُرفع عند فشل استخراج تسلسل CDS ناضج صالح."""


def _reverse_complement(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1]


def extract_mature_cds(
    genomic_sequence: str,
    genomic_sequence_start: int,
    exons: List[dict],
    cds_start: int,
    cds_end: int,
    strand: str,
) -> str:
    """
    Parameters
    ----------
    genomic_sequence : التسلسل الجينومي الخام (مريض أو سليم) — لازم يغطي
                        كامل حدود الجين على الأقل (تمّ التأكد بمرحلة سابقة)
    genomic_sequence_start : الموقع الجينومي (0-based) لأول حرف بـ genomic_sequence
    exons : قائمة الإكسونات {"start": int, "end": int} بإحداثيات جينومية 0-based
    cds_start, cds_end : حدود الـ CDS الجينومية (0-based, half-open)
    strand : "+" أو "-"

    Returns
    -------
    str: تسلسل CDS الناضج (بدون UTR، بدون انترونات)، بالاتجاه الصحيح
         للترجمة المباشرة (5' -> 3' بترتيب الترجمة الفعلي)

    Raises
    ------
    SplicingError لو أي جزء من الـ CDS طلع برا حدود التسلسل الجينومي
                  المعطى (يعني التسلسل المتوفر غير كافٍ)
    """
    coding_pieces: List[str] = []

    for exon in exons:
        piece_start = max(exon["start"], cds_start)
        piece_end = min(exon["end"], cds_end)

        if piece_start >= piece_end:
            continue  # هاد الإكسون بالكامل خارج الـ CDS (UTR بحت) — نتجاهله

        local_start = piece_start - genomic_sequence_start
        local_end = piece_end - genomic_sequence_start

        if local_start < 0 or local_end > len(genomic_sequence):
            raise SplicingError(
                f"جزء من الـ CDS (جينومياً {piece_start}-{piece_end}) يقع خارج "
                f"حدود التسلسل الجينومي المتوفر (يغطي {genomic_sequence_start}-"
                f"{genomic_sequence_start + len(genomic_sequence)}) — "
                f"التسلسل المُدخل غير كافٍ لتغطية الجين كاملاً."
            )

        coding_pieces.append(genomic_sequence[local_start:local_end])

    if not coding_pieces:
        raise SplicingError("لم يتم استخراج أي قطعة CDS صالحة — تحقق من حدود الإكسونات/CDS.")

    if strand == "-":
        reversed_pieces = [_reverse_complement(p) for p in reversed(coding_pieces)]
        mature_cds = "".join(reversed_pieces)
    elif strand == "+":
        mature_cds = "".join(coding_pieces)
    else:
        raise SplicingError(f"قيمة strand غير صالحة: '{strand}' — يجب أن تكون '+' أو '-'")

    logger.info(
        "[Splicer] تم استخراج CDS ناضج (strand=%s): %d قاعدة من %d إكسون مساهم",
        strand, len(mature_cds), len(coding_pieces),
    )
    return mature_cds

def extract_mature_cds_with_position_map(
    genomic_sequence: str,
    genomic_sequence_start: int,
    exons: List[dict],
    cds_start: int,
    cds_end: int,
    strand: str,
) -> tuple[str, List[int]]:
    """
    نفس منطق extract_mature_cds بالضبط، بس بترجع كمان position_map:
    لستة فيها الموقع الجينومي الحقيقي (0-based) لكل حرف بالـ CDS الناضج،
    بنفس الترتيب تماماً (index i بالـ CDS <-> position_map[i] بالجينوم).

    هاي ضرورية لاحقاً بـ translator.py لحساب genomic_position لكل كودون
    (كل 3 قواعد متتالية بـ position_map).

    Returns
    -------
    (mature_cds: str, position_map: List[int])
    """
    coding_pieces: List[str] = []
    position_pieces: List[List[int]] = []

    for exon in exons:
        piece_start = max(exon["start"], cds_start)
        piece_end = min(exon["end"], cds_end)

        if piece_start >= piece_end:
            continue

        local_start = piece_start - genomic_sequence_start
        local_end = piece_end - genomic_sequence_start

        if local_start < 0 or local_end > len(genomic_sequence):
            raise SplicingError(
                f"جزء من الـ CDS (جينومياً {piece_start}-{piece_end}) يقع خارج "
                f"حدود التسلسل الجينومي المتوفر."
            )

        coding_pieces.append(genomic_sequence[local_start:local_end])
        # المواقع الجينومية الحقيقية لهاد الجزء بالضبط (متسلسلة تصاعدياً دايماً هون،
        # بغض النظر عن الـ strand — لأنها لسا إحداثيات جينوم خام)
        position_pieces.append(list(range(piece_start, piece_end)))

    if not coding_pieces:
        raise SplicingError("لم يتم استخراج أي قطعة CDS صالحة.")

    if strand == "-":
        # نفس منطق القلب المستخدم للتسلسل، بنطبقه بالضبط على المواقع كمان:
        # كل قطعة بتنقلب لحالها (reverse فقط، المواقع ما إلها complement)،
        # وبعدين القطع بترتيب معكوس — تماماً متل التسلسل النووي.
        reversed_seq_pieces = [_reverse_complement(p) for p in reversed(coding_pieces)]
        reversed_pos_pieces = [list(reversed(p)) for p in reversed(position_pieces)]

        mature_cds = "".join(reversed_seq_pieces)
        position_map = [pos for piece in reversed_pos_pieces for pos in piece]

    elif strand == "+":
        mature_cds = "".join(coding_pieces)
        position_map = [pos for piece in position_pieces for pos in piece]
    else:
        raise SplicingError(f"قيمة strand غير صالحة: '{strand}'")

    if len(mature_cds) != len(position_map):
        # حارس أمان — ما لازم يصير أبداً لو المنطق صحيح، بس نفضّل نكشفها فوراً
        raise SplicingError(
            f"عدم تطابق طول CDS ({len(mature_cds)}) مع position_map ({len(position_map)}) — "
            f"خلل داخلي بمنطق القص."
        )

    logger.info(
        "[Splicer] CDS + position_map (strand=%s): %d قاعدة، %d قطعة",
        strand, len(mature_cds), len(coding_pieces),
    )
    return mature_cds, position_map