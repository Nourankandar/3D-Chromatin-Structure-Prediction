"""
main_test_hic.py
====================================================================
هاد الملف بيستدعي predictorHIC.py و Get_hic.py الحقيقيين تبعك مباشرة
(بدون أي تعديل عليهن) — بالضبط متل ما رح يصير بالـ pipeline الحقيقي.

اللي بيعمله:
  1. يجهّز django.conf.settings يدوياً (MEDIA_ROOT فقط)
  2. يتحقق: هل عندك best_model.pt حقيقي بمسار ai_engine/models/hi_c/؟
     - لو موجود -> بيستخدمه كما هو (بدون أي تعديل على predict_hic)
     - لو مش موجود -> بيبني ChromogenModel() فاضي وبيحفظ أوزانه العشوائية
       كـ best_model.pt مؤقت، بس للتأكد من إنه التحميل (load_state_dict)
       والـ forward pass شغالين صح من ناحية الشكل (shapes) — نفس منطق
       تجربة الـ DNase سابقاً
  3. يشغّل generate_hic_matrices() الحقيقية على:
     - تسلسل قصير (أقل من نافذة الموديل 1.28M) -> مسار padding
     - تسلسل يستخدم DNA array one-hot جاهز (لتفادي conv على 1.28M كامل كل مرة)
  4. يتحقق: الملف .npz محفوظ، المصفوفة متناظرة (symmetric)، القطر أعلى قيمة،
     الأبعاد صحيحة

⚠️ ملاحظة الأداء: تشغيل الموديل الكامل على نافذة 1,280,000bp حقيقية
على CPU بياخد وقت (دقايق مش ثواني) حتى بأوزان عشوائية، لأنه المعمارية
فيها conv1d عملاقة + attention. هاد طبيعي وليس خطأ.

شغّل بـ: python3 main_test_hic.py
====================================================================
"""
import os
import sys
import time
import tempfile
import shutil

import numpy as np
import torch

# ── 1. تجهيز Django settings يدوياً ──────────────────────────────────────
MEDIA_ROOT = tempfile.mkdtemp(prefix="media_root_hic_")

import django
from django.conf import settings as django_settings
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if not django_settings.configured:
    django_settings.configure(MEDIA_ROOT=MEDIA_ROOT, USE_TZ=True)
    django.setup()

print(f"[Setup] MEDIA_ROOT مؤقت: {MEDIA_ROOT}\n")


# ── 2. التحقق من وجود best_model.pt الحقيقي ──────────────────────────────
from ai_engine.models.hi_c.Get_hic import ChromogenModel

HIC_MODEL_DIR = os.path.join(project_root, "ai_engine", "models", "hi_c")
REAL_MODEL_PATH = os.path.join(HIC_MODEL_DIR, "best_model.pt")

real_weights_available = os.path.exists(REAL_MODEL_PATH)

if not real_weights_available:
    print("⚠️  best_model.pt غير موجود — عم نبني أوزان عشوائية مؤقتة للتأكد من الميكانيكا فقط.")
    print("    لو عندك الملف الحقيقي، حطه بـ ai_engine/models/hi_c/best_model.pt وشغّل هاد الملف تاني.\n")

    torch.manual_seed(42)
    dummy_model = ChromogenModel()
    dummy_model.eval()
    torch.save(dummy_model.state_dict(), REAL_MODEL_PATH)
    print(f"[Setup] أوزان عشوائية مؤقتة اتحفظت بـ: {REAL_MODEL_PATH}\n")
else:
    print("✅ best_model.pt موجود فعلياً — رح يُستخدم كما هو بدون أي تعديل.\n")


# ── 3. استيراد الجسر الحقيقي (predictorHIC.py) بدون أي تعديل ────────────
from backend.services.genomics.HI_C.predictorHIC import (
    generate_hic_matrices,
    encode_dna_one_hot,
    MODEL_WINDOW_SIZE,
    MODEL_NUM_BINS,
    DEFAULT_RESOLUTION,
)
from ai_engine.models.hi_c.Get_hic import predict_hic


def make_random_dna(length: int, seed: int = 0) -> str:
    rng = np.random.default_rng(seed)
    return "".join(rng.choice(list("ACGT"), size=length))


# ── 4. تجربة 1: استدعاء predict_hic() مباشرة بأبعاد صغيرة اصطناعية ───────
# (بس للتأكد من إنه forward pass للموديل نفسه شغال صح على مدخلات مصغّرة
#  ومطابقة تماماً لما بيتوقعه num_bins=256 — بدون تعديل أي كود، فقط نمرر
#  مدخلات مطابقة للأبعاد الحقيقية المتوقعة)
def test_predict_hic_direct():
    print("="*70)
    print("[TEST 1] استدعاء predict_hic() مباشرة (forward pass أساسي)")
    print("="*70)

    dna_array = np.random.rand(1, 4, MODEL_WINDOW_SIZE).astype(np.float32)
    # normalize كـ one-hot تقريبي (مش لازم يكون one-hot حقيقي لتجربة الشكل)
    dnase_array = np.random.rand(1, MODEL_NUM_BINS).astype(np.float32)

    t0 = time.time()
    hic_output = predict_hic(dna_array, dnase_array, model_path=REAL_MODEL_PATH)
    elapsed = time.time() - t0

    print(f"⏱  استغرق: {elapsed:.1f} ثانية")
    print(f"✅ الشكل الناتج: {hic_output.shape} (المتوقع: ({MODEL_NUM_BINS}, {MODEL_NUM_BINS}))")

    assert hic_output.shape == (MODEL_NUM_BINS, MODEL_NUM_BINS), \
        f"❌ FAIL: شكل خاطئ {hic_output.shape}"
    assert not np.isnan(hic_output).any(), "❌ FAIL: فيه NaN بالمخرجات"

    # تحقق من التناظر التقريبي (الموديل نفسه بيعمل (out + out.T) * 0.5 بالداخل)
    np.testing.assert_array_almost_equal(hic_output, hic_output.T, decimal=4)
    print("✅ المصفوفة متناظرة (symmetric) كما هو متوقع من معمارية pair_proj_i/j")
    print(f"   min={hic_output.min():.4f}  max={hic_output.max():.4f}  mean={hic_output.mean():.4f}\n")

    return hic_output


# ── 5. تجربة 2: generate_hic_matrices() الحقيقية - مسار التسلسل القصير ──
def test_generate_hic_short_sequence():
    print("="*70)
    print("[TEST 2] generate_hic_matrices() - تسلسل قصير (أقل من نافذة الموديل)")
    print("="*70)

    # تسلسل صغير عمداً (5000bp) حتى يكون أقل من MODEL_WINDOW_SIZE
    # وبالتالي يدخل مسار الـ padding مباشرة (سطر واحد استدعاء لـ predict_hic)
    seq_len = 5000
    dna_seq = make_random_dna(seq_len, seed=1)
    dnase_signal = np.random.rand(seq_len).astype(np.float32)

    t0 = time.time()
    relative_path = generate_hic_matrices(
        dna_input=dna_seq,
        dnase_input=dnase_signal,
        output_name_hint="test_patient_short",
    )
    elapsed = time.time() - t0
    print(f"⏱  استغرق: {elapsed:.1f} ثانية")

    absolute_path = os.path.join(MEDIA_ROOT, relative_path)
    assert os.path.exists(absolute_path), f"❌ FAIL: الملف مش موجود {absolute_path}"

    with np.load(absolute_path) as data:
        hic_matrix = data["hic_matrix"]
        resolution = int(data["resolution"])
        end = int(data["end"])

    print(f"✅ الملف محفوظ: {relative_path}")
    print(f"✅ شكل المصفوفة: {hic_matrix.shape}")
    print(f"✅ resolution={resolution}, end={end}")

    assert hic_matrix.shape[0] == hic_matrix.shape[1], "❌ FAIL: المصفوفة مش مربعة"
    assert not np.isnan(hic_matrix).any(), "❌ FAIL: فيه NaN"
    np.testing.assert_array_almost_equal(hic_matrix, hic_matrix.T, decimal=4)
    print("✅ المصفوفة متناظرة")

    # القطر لازم يكون أعلى قيمة (حسب np.fill_diagonal(hic_matrix, hic_matrix.max()))
    assert np.allclose(np.diagonal(hic_matrix), hic_matrix.max()), \
        "❌ FAIL: القطر مش مساوي لأعلى قيمة كما متوقع من الكود"
    print(f"✅ القطر = أعلى قيمة بالمصفوفة ({hic_matrix.max():.4f}) كما هو متوقع\n")

    return hic_matrix


# ── 6. تجربة 3: encode_dna_one_hot (تأكيد سريع، pure numpy، بدون موديل) ──
def test_encode_dna_one_hot():
    print("="*70)
    print("[TEST 3] encode_dna_one_hot() - تحقق منطقي بدون موديل")
    print("="*70)

    encoded = encode_dna_one_hot("ACGT", target_len=4)
    assert encoded.shape == (1, 4, 4)
    assert encoded[0, 0, 0] == 1.0  # A -> index 0
    assert encoded[0, 3, 3] == 1.0  # T -> index 3
    print("✅ الترميز one-hot صحيح لكل قاعدة")

    encoded_n = encode_dna_one_hot("ACGN", target_len=4)
    assert encoded_n[0, :, 3].sum() == 0.0  # N -> صفر بكل القنوات
    print("✅ القواعد غير المعروفة (N) بتترمز كأصفار وليس عشوائي\n")


if __name__ == "__main__":
    try:
        test_encode_dna_one_hot()
        test_predict_hic_direct()
        test_generate_hic_short_sequence()

        print("="*70)
        print("✅ كل التجارب نجحت — predictorHIC.py و Get_hic.py شغالين end-to-end")
        print("   بدون أي تعديل على الكود الأصلي.")
        if not real_weights_available:
            print("⚠️  بس تذكر: هاي أوزان عشوائية (best_model.pt مؤقت). لتأكيد الدقة")
            print("    الفعلية، حط أوزانك الحقيقية بنفس المسار وشغّل الملف تاني.")
        print("="*70)
    finally:
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        if not real_weights_available and os.path.exists(REAL_MODEL_PATH):
            os.remove(REAL_MODEL_PATH)
            print(f"\n[Cleanup] شلنا best_model.pt المؤقت يلي بنيناه للتجربة.")
