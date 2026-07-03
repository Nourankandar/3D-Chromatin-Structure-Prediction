import os
import sys
import numpy as np

# 1. جلب المسار الحالي لملف التست (الموجود داخل مجلد test)
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. الانتقال خطوة للخلف للوصول إلى الجذر الأساسي للمشروع (Root)
root_dir = os.path.abspath(os.path.join(current_dir, '..'))

# 3. إضافة الـ Root إلى مسارات بايثون قبل عمل الـ Import
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 4. الآن سيتم التعرف على المسار بدون أي مشاكل
from ai_engine.models.hi_c.Get_hic import predict_hic

if __name__ == "__main__":
    print("تم حل مشكلة الـ Import والتعرف على المسار بنجاح! 🎉")
    
    # ══════════════════════════════════════════════════════════════
    # تعديل أبعاد البيانات الوهمية لتتوافق مع المودل الحقيقي
    # ══════════════════════════════════════════════════════════════
    # المودل يتوقع الـ DNA بأبعاد: (Batch_size, Channels, Length)
    # القنوات يجب أن تكون 4 (A, C, G, T) وطول التسلسل لنفترضه 1000 خطوة كمثال
    seq_length = 1280000 
    num_bins = 256
    
    # الـ DNA يمر عبر التصغير ليصل إلى 256
    mock_dna = np.random.randn(1, 4, seq_length).astype(np.float32)
    
    # الـ DNase يجب أن يُمرر بحجم الـ bins مباشرة ليتم دمج القنوات بسلاسة بيب
    mock_dnase = np.random.randn(1, num_bins).astype(np.float32)
    try:
        print("جاري استدعاء التابع للتنبؤ...")
        # استدعاء التابع
        predicted_matrix = predict_hic(mock_dna, mock_dnase)
        print(f"أبعاد مصفوفة الـ Hi-C المستخرجة: {predicted_matrix.shape}")
    except Exception as e:
        print(f"ظهر خطأ أثناء التشغيل: {e}")