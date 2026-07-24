"""
core/utils/genomics_utils.py
====================================================================
دوال مساعدة صغيرة مشتركة تخص التعامل مع بيانات جينومية عامة
(اسم كروموسوم، تنسيقات، إلخ) — تُستخدم بأكثر من مكان بالـ pipeline.
====================================================================
"""


def normalize_chromosome_name(chromosome: str) -> str:
    """
    يرجع اسم الكروموسوم موحّد الشكل دايماً بصيغة 'chr21' (مع chr وحدة بس)،
    بغض النظر إذا المستخدم بعت '21' أو 'chr21' أو 'Chr21'.
    """
    chromosome = str(chromosome).strip()
    if chromosome.lower().startswith("chr"):
        return "chr" + chromosome[3:]
    return f"chr{chromosome}"

import numpy as np


def call_dnase_peaks(dnase_signal: np.ndarray, min_fraction_of_max: float = 0.5, 
                       min_peak_width: int = 10, absolute_min_signal: float = 0.01) -> list[tuple[int, int]]:
    """
    يحدد مناطق الانفتاح (peaks) من إشارة DNase.
    
    لو الإشارة كلها ضعيفة جداً (زي منطقة كروماتين مقفولة بيولوجياً)،
    منرجع قائمة فاضية بدل ما نعتبر كل شي "peak" غلط.
    """
    if dnase_signal is None or len(dnase_signal) == 0:
        return []

    max_val = dnase_signal.max()

    # لو أعلى قيمة بكل التسلسل أصلاً ضعيفة جداً (كروماتين مقفول حقيقي)
    # منعتبر المنطقة كلها "مقفولة" ومنرجع peaks فاضية بدل فلترة خاطئة
    if max_val < absolute_min_signal:
        return []

    threshold_value = max_val * min_fraction_of_max
    above_threshold = dnase_signal >= threshold_value

    peaks = []
    start = None
    for i, is_above in enumerate(above_threshold):
        if is_above and start is None:
            start = i
        elif not is_above and start is not None:
            if i - start >= min_peak_width:
                peaks.append((start, i))
            start = None
    if start is not None and len(dnase_signal) - start >= min_peak_width:
        peaks.append((start, len(dnase_signal)))

    return peaks

def is_position_in_peaks(position: int, peaks: list) -> bool:
    """
    يتحقق إذا كان موقع معيّن (index) واقع جوا أي منطقة انفتاح (DNase peak).
    peaks: لستة من (start, end) tuples طالعة من call_dnase_peaks — بنفس
    وحدة الـ position (index داخل مصفوفة الإشارة).
    """
    for start, end in peaks:
        if start <= position < end:
            return True
    return False