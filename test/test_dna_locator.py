import os
import sys

# 1. جلب المسارات
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
backend_dir = os.path.join(root_dir, 'backend')

if root_dir not in sys.path: sys.path.insert(0, root_dir)
if backend_dir not in sys.path: sys.path.insert(0, backend_dir)

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings") 
django.setup()

from backend.services.genomics.referenceGenome.DNA_locator import locate_patient_sequence, SequenceLocationError
import backend.services.genomics.referenceGenome.DNA_locator as dna_locator

if __name__ == "__main__":
    print("🎉 تم التعرف على المسارات واستيراد الدالة بنجاح!")
    
    from django.conf import settings
    from pyfaidx import Fasta
    
    genome_fa_path = os.path.join(settings.GENOME_REFERENCE_ROOT, "genome.fa")
    patient_fasta_sample = os.path.join(root_dir, "media", "sample_patient.fasta")
    
    # ─── كشف اللعبة: سنقرأ الكروموسوم بنفس طريقة الكود تماماً ونرى ماذا يوجد بداخله ───
    print("👀 جاري فحص عينة من الكروموسوم '1' في الجينوم المرجعي...")
    genome = Fasta(genome_fa_path, rebuild=False)
    
    # تحديد المفتاح الصحيح للكروموسوم المتوفر
    chrom_key = "1" if "1" in genome.keys() else list(genome.keys())[:5][0]
    
    # سحب أول 300 حرف حقيقي من الكروموسوم
    full_chrom_preview = str(genome[chrom_key][:]).upper()
    genome.close()
    
    # تنظيف النص من أي فراغات أو أحرف N مجهولة وأخذ قطعة بطول 150 حرف
    clean_preview = "".join([c for c in full_chrom_preview if c in "ACGT"])
    
    if len(clean_preview) > 60000:
        real_sequence = clean_preview[50000:50150] # نأخذ 150 حرف من منطقة فريدة داخل الكروموسوم
    else:
        # إذا كان الكروموسوم المستخرج صغيراً اصلاً، نأخذ قطعة من المنتصف
        mid = len(clean_preview) // 2
        real_sequence = clean_preview[mid:mid+150]
    
    print(f"🔬 أول 50 حرف تم قراءتها فعلياً: {clean_preview[:50]}")
    print(f"🧬 التسلسل المستهدف للفحص (طوله {len(real_sequence)}bp): {real_sequence}")
    
    # كتابة هذا التسلسل النقي في ملف المريض
    os.makedirs(os.path.dirname(patient_fasta_sample), exist_ok=True)
    with open(patient_fasta_sample, "w") as f:
        f.write(f">patient_sequence_perfect_match\n{real_sequence}\n")
        
    # ─── تعديل الإعدادات لتكون مرنة وقاتلة للأخطاء ───
    dna_locator.SEED_STRIDE = 10       # تصغير القفزة لإنتاج Seeds بكثافة عالية جداً
    dna_locator.SEED_LENGTH = 20       # تقصير طول الـ Seed لسهولة المطابقة
    dna_locator.MIN_SEEDS_REQUIRED = 1 # نكتفي بـ Seed واحد لإيجاد الموقع
    dna_locator.MIN_IDENTITY = 0.70    # خفض شرط المطابقة النهائي لتسهيل الفحص
    
    try:
        print(f"🔍 تشغيل الخوارزمية الآن الموجهة للكروموسوم '{chrom_key}'...")
        result = locate_patient_sequence(
            patient_fasta_path=patient_fasta_sample,
            chromosome_hint=chrom_key
        )
        
        print("\n🏆 صفّق الآن!!! تم تحديد الموقع بنجاح خارق!")
        print(f"الكروموسوم: {result['chromosome']}")
        print(f"البداية (Start): {result['start']}")
        print(f"النهاية (End): {result['end']}")
        print(f"الـ Strand: {result['strand']}")
        print(f"نسبة التطابق: {result['identity'] * 100:.2f}%")

    except SequenceLocationError as e:
        print(f"❌ لسه فشل! هاد معناه الـ Seeds عم تطير بسبب وجود أحرف مخفية (أو أن الكروموسوم كله أحرف N مجهولة): {e}")
    except Exception as e:
        print(f"💥 خطأ غير متوقع: {e}")