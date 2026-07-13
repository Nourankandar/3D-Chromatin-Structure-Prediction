import numpy as np
import tensorflow as tf
from ai_engine.models.Dnase.DNASEpredictor import prepare_and_predict_dnase

print("🚀 بدء فحص موديل Enformer اللوكال مع بيانات وهمية...")

print("\n--- [فحص الحالة الأولى: تسلسل أصغر من الطول المستهدف (Padding)] ---")
short_seq = np.zeros((100000, 4), dtype=np.float32)
short_seq[:, 0] = 1.0  

try:
    preds_short = prepare_and_predict_dnase(short_seq)
    print(f"✅ نجح الفحص! الأبعاد المستخرجة للـ DNase: {preds_short.shape}")
except Exception as e:
    print(f"❌ فشل الفحص في الحالة الأولى: {e}")


# 2. تجهيز تسلسل وهمي طويل جداً (مثلاً: طوله 500,000 قاعدة) عشان نختبر الـ Sliding Windows والدمج
print("\n--- [فحص الحالة الثانية: تسلسل أكبر من الطول المستهدف (Sliding Windows)] ---")
long_seq = np.zeros((500000, 4), dtype=np.float32)
long_seq[:, 1] = 1.0  # قيمة وهمية لـ One-Hot

try:
    preds_long = prepare_and_predict_dnase(long_seq)
    print(f"✅ نجح الفحص! الأبعاد المستخرجة للـ DNase المدمج: {preds_long.shape}")
except Exception as e:
    print(f"❌ فشل الفحص في الحالة الثانية: {e}")

print("\n🎉 انتهى الفحص بالكامل!")