"""
services/genomics/DNASE/nucleosome_track.py
====================================================================
يبني طبقة "نيوكليوزوم" (sub-bin resolution) فوق مسار الـ 3D الجاهز
(coords_smooth من coords_service.py)، بالاعتماد على نفس مصفوفة DNase
الخام المستخدمة أصلاً بالـ Hi-C وبـ scanner.py.

المنطق البيولوجي (مبسّط كتقريب عملي — proxy، مش نموذج نيوكليوزوم حقيقي
زي NucleoATAC، لأنه ما عنا بيانات MNase-seq):
  - كل نيوكليوزوم ~200bp (147bp ملتفة حول الهيستونات + ~50-60bp linker).
  - DNase I بيقدر يقطع بس بالمناطق المكشوفة (بين النيوكليوزومات أو
    بمناطق NFR) — فإشارة DNase واطية = محمي/ملفوف حول الهيستون،
    وإشارة عالية = مكشوف/منفرد.
  - هاد نفس المبدأ العلمي يلي تجربة DNase-seq نفسها مبنية عليه.
====================================================================
"""

import logging
from typing import List, TypedDict

import numpy as np

logger = logging.getLogger(__name__)

NUCLEOSOME_PERIOD_BP = 200   # 147 wrapped + ~53 linker (تقريب قياسي بيولوجياً)
DEFAULT_OPEN_FRACTION_OF_MAX = 0.3  # threshold ابتدائي — لازم يُعاير على GAPDH/ACTB قبل الاعتماد عليه


class NucleosomeUnit(TypedDict):
    unit_index: int
    genomic_start: int
    genomic_end: int
    state: str          # "wrapped" | "open"
    dnase_signal: float
    x: float
    y: float
    z: float


def build_nucleosome_track(
    dnase_signal: np.ndarray,
    coords_smooth: list,
    genomic_start: int,
    n_original_bins: int,
    resolution: int,
    open_fraction_of_max: float = DEFAULT_OPEN_FRACTION_OF_MAX,
) -> List[NucleosomeUnit]:
    """
    Parameters
    ----------
    dnase_signal    : المصفوفة الخام (نفس raw_signal المستخدمة بـ predictorHIC.py)
    coords_smooth   : مخرجات build_structure() بـ coords_service.py (منحنى ناعم، عادة 1200 نقطة)
    genomic_start   : بداية المنطقة الحقيقية بالـ bp (من coords['start'])
    n_original_bins : عدد الـ bins الأصلية بالـ Hi-C (len(coords_raw)) — لحساب الطول الكلي بدقة
    resolution      : دقة الـ Hi-C bin (عادة 5000)
    open_fraction_of_max : نسبة من أعلى إشارة DNase تُعتبر فوقها "مفتوح" — قيمة ابتدائية،
                            لازم تُعاير عملياً (راجع الملاحظة بالأسفل)

    Returns
    -------
    list[NucleosomeUnit]: قائمة وحدات بطول ~200bp لكل وحدة، كل وحدة فيها موقعها
    الجينومي، حالتها (wrapped/open)، وموقعها x,y,z على المسار الناعم — جاهزة
    مباشرة للفرونت يرسم عليها الالتفاف أو الخط المفرود.
    """
    if len(coords_smooth) < 2:
        logger.warning("[NucleosomeTrack] coords_smooth قليل جداً (%d نقطة) — تخطي البناء", len(coords_smooth))
        return []

    total_bp = n_original_bins * resolution
    if total_bp <= 0:
        logger.warning("[NucleosomeTrack] total_bp غير صالح (n_original_bins=%d) — تخطي البناء", n_original_bins)
        return []

    max_signal = float(dnase_signal.max()) if len(dnase_signal) and dnase_signal.max() > 0 else 1.0
    threshold = max_signal * open_fraction_of_max

    n_units = max(1, total_bp // NUCLEOSOME_PERIOD_BP)
    n_smooth = len(coords_smooth)

    track: List[NucleosomeUnit] = []
    n_open = 0

    for i in range(n_units):
        unit_start_bp = i * NUCLEOSOME_PERIOD_BP
        unit_end_bp = unit_start_bp + NUCLEOSOME_PERIOD_BP

        if unit_start_bp >= len(dnase_signal):
            break  # تجاوزنا طول الإشارة الفعلي المتوفر

        segment = dnase_signal[unit_start_bp: min(unit_end_bp, len(dnase_signal))]
        avg_signal = float(segment.mean()) if len(segment) else 0.0
        state = "open" if avg_signal >= threshold else "wrapped"
        if state == "open":
            n_open += 1

        # تحويل موقع الوحدة (نسبة من طول المنطقة) لأقرب نقطة على المنحنى الناعم
        fraction = unit_start_bp / total_bp
        smooth_idx = min(int(fraction * (n_smooth - 1)), n_smooth - 1)
        point = coords_smooth[smooth_idx]

        track.append({
            "unit_index": i,
            "genomic_start": genomic_start + unit_start_bp,
            "genomic_end": genomic_start + unit_end_bp,
            "state": state,
            "dnase_signal": round(avg_signal, 4),
            "x": point["x"],
            "y": point["y"],
            "z": point["z"],
        })

    logger.info(
        "[NucleosomeTrack] تم بناء %d وحدة (threshold=%.4f) — مفتوح: %d (%.0f%%)، ملفوف: %d (%.0f%%)",
        len(track), threshold, n_open, 100 * n_open / max(len(track), 1),
        len(track) - n_open, 100 * (len(track) - n_open) / max(len(track), 1),
    )

    return track