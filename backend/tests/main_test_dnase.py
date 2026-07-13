"""
main_test_dnase.py
====================================================================
هاد الملف بيستدعي predictor.py الحقيقي تبعك مباشرة (services/DNASE/predictor.py)
بدون أي تعديل أو نسخة بديلة عنه — بالضبط متل ما رح يصير بالـ pipeline الحقيقي.

اللي بيعمله هاد الملف:
  1. يجهّز django.conf.settings يدوياً (configure) بس بـ MEDIA_ROOT، لأنه
     ما عنا مشروع Django كامل هون — لو عندك مشروع حقيقي، هاد الجزء مش لازم،
     Django بيكون already configured.
  2. يبني ملف FASTA حقيقي مؤقت (تسلسل عشوائي، أو حط تسلسل حقيقي إذا بدك)
  3. لو الأوزان الحقيقية (C:\\Users\\dell\\.kipoi\\models\\Basset) موجودة
     بهاد الجهاز -> بيستخدمها كما هي (بدون أي تغيير على load_basset_model)
     لو مش موجودة -> بيعمل monkeypatch مؤقت لـ load_basset_model بس تشتغل
     التجربة بأوزان عشوائية (تأكيد ميكانيكا فقط، مش دقة)
  4. يستدعي predict_dnase_profiles() نفسها (من predictor.py) بدون أي تغيير
  5. يتحقق من: الملف انحفظ، الأبعاد صحيحة، القيم منطقية (0-1، بدون NaN)

شغّل بـ: python3 main_test_dnase.py
====================================================================
"""
import os
import sys
import tempfile
import shutil
# العودة خطوتين للخلف من مجلد DNASE للوصول إلى المجلد الرئيسي للمشروع
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ── المسار الجذر (عدّله عندك لمسار مشروعك الفعلي لو مختلف) ─────────────
PROJECT_ROOT = "/home/claude"
sys.path.insert(0, PROJECT_ROOT)

import numpy as np

# ── 1. تجهيز Django settings يدوياً (بس MEDIA_ROOT) ─────────────────────
MEDIA_ROOT = tempfile.mkdtemp(prefix="media_root_")

import django
from django.conf import settings as django_settings

if not django_settings.configured:
    django_settings.configure(MEDIA_ROOT=MEDIA_ROOT, USE_TZ=True)
    django.setup()

print(f"[Setup] MEDIA_ROOT مؤقت: {MEDIA_ROOT}\n")


# ── 2. التحقق: هل الأوزان الحقيقية موجودة بهاد الجهاز؟ ──────────────────
REAL_WEIGHTS_DIR = r"C:\Users\dell\.kipoi\models\Basset"
real_weights_available = os.path.exists(REAL_WEIGHTS_DIR)

if not real_weights_available:
    print("⚠️  الأوزان الحقيقية غير موجودة بهاد الجهاز (مسار ويندوز محلي).")
    print("    عم نستخدم أوزان عشوائية (random init) للتأكد من الميكانيكا فقط.")
    print("    لو شغّلت هاد الملف عندك (وين الأوزان موجودة فعلياً)، رح تستخدم")
    print("    load_basset_model() الحقيقية تبعك تلقائياً بدون أي تعديل.\n")

    import torch
    from ai_engine.models.Dnase import model_loader as real_model_loader

    def _fake_load_basset_model(weights_path=None):
        torch.manual_seed(42)
        model = real_model_loader.BassetModel()
        model.eval()
        real_model_loader._model = model
        return model

    # monkeypatch مؤقت فقط لهاي التجربة
    real_model_loader.load_basset_model = _fake_load_basset_model
    real_model_loader._model = None
else:
    print("✅ الأوزان الحقيقية موجودة — رح تنستخدم load_basset_model() الأصلية بدون أي تعديل.\n")


# ── 3. استيراد الجسر الحقيقي (predictor.py) بدون أي تعديل ──────────────
from services.DNASE.predictor import predict_dnase_profiles, read_fasta_file


# ── 4. بناء ملف FASTA حقيقي مؤقت ────────────────────────────────────────
def make_test_fasta(length=3000, seed=1) -> str:
    rng = np.random.default_rng(seed)
    sequence = "".join(rng.choice(list("ACGT"), size=length))

    fasta_dir = os.path.join(MEDIA_ROOT, "genomics", "sequences")
    os.makedirs(fasta_dir, exist_ok=True)
    fasta_path = os.path.join(fasta_dir, "patient_test_input.fasta")

    with open(fasta_path, "w") as f:
        f.write(">patient_test_input\n")
        for i in range(0, len(sequence), 60):
            f.write(sequence[i:i+60] + "\n")

    return fasta_path, sequence


# ── 5. التشغيل الفعلي عبر predictor.py الحقيقي ──────────────────────────
def main():
    print("="*70)
    print("تجربة: استدعاء predict_dnase_profiles() الحقيقية من predictor.py")
    print("="*70)

    fasta_path, original_seq = make_test_fasta(length=3000, seed=1)
    print(f"[FASTA] ملف مؤقت أنشئ: {fasta_path} ({len(original_seq)} bp)\n")

    # تحقق أولي: read_fasta_file() الحقيقية عم تقرا صح
    read_back = read_fasta_file(fasta_path)
    assert read_back == original_seq, "❌ FAIL: read_fasta_file لم يطابق التسلسل الأصلي"
    print("✅ read_fasta_file() قرأت التسلسل بشكل مطابق تماماً\n")

    # الاستدعاء الفعلي لنفس الدالة التي يستدعيها GenomicPipelineManager
    enformer_id = 12
    relative_output_path = predict_dnase_profiles(
        fasta_absolute_path=fasta_path,
        enformer_id=enformer_id,
    )

    print(f"\n[Bridge] predict_dnase_profiles() رجعت المسار: {relative_output_path}")

    # ── تحقق من النتيجة ──
    absolute_output_path = os.path.join(MEDIA_ROOT, relative_output_path)
    assert os.path.exists(absolute_output_path), f"❌ FAIL: الملف مش موجود {absolute_output_path}"

    saved_scores = np.load(absolute_output_path)

    assert saved_scores.shape == (3000,), f"❌ FAIL: الشكل {saved_scores.shape} != (3000,)"
    assert not np.isnan(saved_scores).any(), "❌ FAIL: فيه NaN بالنتائج"
    assert 0.0 <= saved_scores.min() and saved_scores.max() <= 1.0, "❌ FAIL: القيم خارج مجال [0,1]"
    assert f"track_{enformer_id}" in relative_output_path, "❌ FAIL: اسم الملف ما فيه رقم الـ track الصحيح"
    assert relative_output_path.startswith("genomics/predicted_dnase/"), "❌ FAIL: المسار النسبي غلط"

    print(f"✅ الملف موجود فعلياً على القرص: {absolute_output_path}")
    print(f"✅ الأبعاد صحيحة: {saved_scores.shape}")
    print(f"✅ القيم كلها ضمن [0,1] وبدون NaN")
    print(f"✅ اسم الملف يحتوي track الصحيح ({enformer_id})")
    print(f"   min={saved_scores.min():.4f}  max={saved_scores.max():.4f}  mean={saved_scores.mean():.4f}")

    print("\n" + "="*70)
    print("✅ predictor.py (الجسر الحقيقي) اشتغل end-to-end بدون أي تعديل عليه.")
    if not real_weights_available:
        print("⚠️  بس تذكر: هاي أوزان عشوائية. لتأكيد الدقة الفعلية، شغّل هاد")
        print("    الملف عندك حيث تتوفر أوزان Basset الحقيقية.")
    print("="*70)


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
