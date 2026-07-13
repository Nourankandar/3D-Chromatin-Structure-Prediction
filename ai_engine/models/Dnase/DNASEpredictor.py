"""
predictor.py -- Basset sliding window predictor
Any sequence length: short (padding) or long (sliding windows)
"""
import numpy as np
import torch
from scipy.ndimage import gaussian_filter1d
BASSET_WINDOW = 600
BASSET_TRACKS = 164

_MAP = {
    'A': [1,0,0,0], 'C': [0,1,0,0], 'G': [0,0,1,0], 'T': [0,0,0,1],
    'a': [1,0,0,0], 'c': [0,1,0,0], 'g': [0,0,1,0], 't': [0,0,0,1],
    'N': [.25,.25,.25,.25], 'n': [.25,.25,.25,.25],
}


def encode_window(seq: str) -> np.ndarray:
    """600bp str -> (1, 4, 600, 1) float32"""
    arr = np.array([_MAP.get(b, _MAP['N']) for b in seq], dtype=np.float32)
    return arr.T[np.newaxis, :, :, np.newaxis]


def _auto_step(n: int) -> int:
    if n <= 5_000:   return 50
    if n <= 50_000:  return 200
    return 500


def _make_windows(seq: str, step: int):
    """Generator: yields (window_600bp, start_pos, is_padded)"""
    n = len(seq)
    if n <= BASSET_WINDOW:
        pad = BASSET_WINDOW - n
        pl  = pad // 2
        yield 'N' * pl + seq + 'N' * (pad - pl), 0, True
        return
    pos = 0
    while pos + BASSET_WINDOW <= n:
        yield seq[pos: pos + BASSET_WINDOW], pos, False
        pos += step
    if pos < n:
        yield seq[n - BASSET_WINDOW: n], n - BASSET_WINDOW, False


def _count_windows(n: int, step: int) -> int:
    if n <= BASSET_WINDOW:
        return 1
    c = (n - BASSET_WINDOW) // step + 1
    return c + (1 if (c - 1) * step + BASSET_WINDOW < n else 0)


def predict_dnase_accessibility(
    sequence: str,
    model=None,
    step: int = None,
    batch_size: int = 32,
    smooth_sigma: float = 30.0,
) -> dict:
    """
    Input : DNA string, any length
    Output: dict with keys:
        scores     -> (Length,)      mean DNase across 164 cell types
        scores_164 -> (Length, 164)  per-cell scores
        n_windows  -> int
        step       -> int used
    """
    if model is None:
        from .model_loader import load_basset_model
        model = load_basset_model()

    n    = len(sequence)
    step = step or _auto_step(n)
    n_win = _count_windows(n, step)

    print(f"[Basset] {n:,} bp | {n_win} windows | step={step} | batch={batch_size}")

    result = np.zeros((n, BASSET_TRACKS), dtype=np.float32)
    counts = np.zeros(n, dtype=np.float32)

    win_buf, meta_buf = [], []

    def _flush():
        batch = torch.from_numpy(np.concatenate(win_buf, axis=0))
        with torch.no_grad():
            preds = model(batch).cpu().numpy()
        for pred, (pos, is_pad) in zip(preds, meta_buf):
            if is_pad:
                pl = (BASSET_WINDOW - n) // 2
                result[0:n] += pred
                counts[0:n] += 1
            else:
                result[pos: pos + BASSET_WINDOW] += pred
                counts[pos: pos + BASSET_WINDOW] += 1
        win_buf.clear()
        meta_buf.clear()

    done = 0
    for win_seq, pos, is_pad in _make_windows(sequence, step):
        win_buf.append(encode_window(win_seq))
        meta_buf.append((pos, is_pad))
        if len(win_buf) == batch_size:
            _flush()
            done += batch_size
            print(f"   [{done/n_win*100:5.1f}%] {done}/{n_win}")

    if win_buf:
        _flush()
        done += len(win_buf)
        print(f"   [100.0%] {done}/{n_win}")

    counts     = np.maximum(counts, 1)
    scores_164 = result / counts[:, np.newaxis]
    scores     = scores_164.mean(axis=1)

    if smooth_sigma > 0:
        scores = gaussian_filter1d(scores, sigma=smooth_sigma)

    print(f"[Basset] done | mean={scores.mean():.3f} | max={scores.max():.3f}")
    return {
        'scores':     scores,
        'scores_164': scores_164,
        'n_windows':  n_win,
        'step':       step,
    }
import os
import sys

# ضبط مسار المشروع الرئيسي ليتعرف بايثون على الـ ai_engine
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# الآن يمكنك عمل Import مطلق بأمان كامل
from ai_engine.models.Dnase.model_loader import load_basset_model

if __name__ == "__main__":
    # 1. استدعاء الموديل وشحن الأوزان
    basset = load_basset_model()
    
    # 2. إنشاء تسلسل DNA طويل جداً (5000 قاعدة) يحتوي على جينات منوعة
    # هذا التسلسل سيتم تقسيمه تلقائياً إلى عدد كبير من النوافذ المتداخلة
    long_dna_sequence = "ATCG" * 1250  # 4 * 1250 = 5000bp
    
    print(f"\n🚀 بدء اختبار البايبلاين على تسلسل طويل جداً بطول: {len(long_dna_sequence):,} bp")
    
    # 3. استدعاء دالة التنبؤ
    # قمنا بضبط الـ step=50 ليعطينا أعلى دقة وتداخل مكثف بين النوافذ
    # وضبطنا الـ batch_size=16 لتشاهد كيف تتم معالجة النوافذ على دفعات
    results = predict_dnase_accessibility(
        sequence=long_dna_sequence, 
        model=basset, 
        step=50, 
        batch_size=16,
        smooth_sigma=30.0
    )
    
    # 4. طباعة وتحليل النتائج المستخرجة
    print("\n📊 --- تحليل مصفوفات النتائج الناجحة ---")
    print(f"✅ أبعاد مصفوفة الـ 164 خلية لكل قاعدة: {results['scores_164'].shape}") 
    print(f"   (هذا يعني أن لديك تنبؤ كامل بدقة Base-pair لكل موقع من المواقع الـ 5000 عبر الـ 164 خلية!)")
    
    print(f"✅ أبعاد مصفوفة المتوسط العام (scores): {results['scores'].shape}")
    print(f"✅ أعلى قيمة احتمالية تم رصدها في الكروموسوم: {results['scores'].max():.4f}")