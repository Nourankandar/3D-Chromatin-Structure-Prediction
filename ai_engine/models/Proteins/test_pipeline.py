import os
import sys

# تأمين إضافة المسار الحالي لضمان التعرف على المجلدات الشقيقة
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# استيراد الكلاسات بناءً على هيكل المجلدات الظاهر في الصورة
from MotifScanner.protein_lookup import GenomicMotifScanner
from ProteinStructures.protein_fetcher import ProteinStructureFetcher

def run_pipeline():
    # 1. تسلسل DNA تجريبي يحتوي على مواقع ربط محتملة (مثل CTCF)
    sample_dna = "GGCAGCCAAGGGGGCAGCTAGGGGTGGCAGCCAAGGGGGCAGCTAGGGG"
    
    print("=== الخطوة 1: فحص تسلسل DNA عن الحوافز (Motifs) ===")
    try:
        # تأكد من وجود ملف JASPAR2022_CORE_vertebrates.jaspar داخل مجلد MotifScanner
        scanner = GenomicMotifScanner()
        
        print(f"جاري فحص التسلسل: {sample_dna[:30]}...")
        detected_motifs = scanner.scan_sequence(sample_dna, threshold=0.8)
        
        if not detected_motifs:
            print("لم يتم العثور على أي بروتينات مرتبطة بهذا التسلسل.")
            return
            
        print(f"تم العثور على {len(detected_motifs)} حافز مرتبط. إليك أول نتيجة:")
        match = detected_motifs[0]
        print(f"  البروتين: {match['protein_name']} | معرف JASPAR: {match['jaspar_id']} | النتيجة: {match['score']}")

    except FileNotFoundError as e:
        print(f"خطأ: تأكد من وضع ملف JASPAR في المجلد الصحيح.\nتفاصيل: {e}")
        return
    except Exception as e:
        print(f"حدث خطأ أثناء الفحص: {e}")
        return

    print("\n=== الخطوة 2: جلب الهيكل البنائي (PDB) ===")
    target_protein = detected_motifs[0]['protein_name']
    
    try:
        # تهيئة جالب الهياكل البنائية (سيقوم بإنشاء الـ cache تلقائياً داخل مجلده)
        fetcher = ProteinStructureFetcher()
        
        print(f"جاري البحث وتنزيل ملف PDB للبروتين: {target_protein}...")
        pdb_file_path = fetcher.fetch(target_protein)
        
        print("\n=== تم العملية بنجاح! ===")
        print(f"مسار ملف الهيكل البنائي المستخرج: {pdb_file_path}")

    except ValueError as e:
        print(f"خطأ في جلب البيانات من السيرفر: {e}")
    except Exception as e:
        print(f"حدث خطأ غير متوقع أثناء جلب الهيكل: {e}")

if __name__ == "__main__":
    run_pipeline()