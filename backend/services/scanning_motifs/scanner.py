# backend/services/scanning_motifs/scanner.py

import os
import numpy as np
from django.conf import settings

# استدعاء المحركات الحسابية من الـ ai_engine المستقل
from ai_engine.models.Proteins.MotifScanner.protein_lookup import GenomicMotifScanner
from ai_engine.models.Proteins.ProteinStructures.protein_fetcher import ProteinStructureFetcher


def run_motif_delta_analysis(fasta_absolute_path: str) -> dict:
    """
    يقرأ ملف الـ FASTA، ويقوم بتشغيل الـ Motif Scanner لاستخراج البروتينات المتأثرة.
    يعيد قاموساً مهيأً ومعرفاً بأسماء البروتينات كـ مفاتيح (Keys).
    """
    # 1. قراءة التسلسل النظيف من ملف الـ FASTA
    with open(fasta_absolute_path, "r") as f:
        lines = f.readlines()
    dna_sequence = "".join(line.strip() for line in lines if not line.startswith(">"))

    # 2. استدعاء الماسح الجينومي
    scanner = GenomicMotifScanner()
    detected_motifs = scanner.scan_sequence(dna_sequence, threshold=0.8)

    # 3. إعادة هيكلة البيانات ليتوافق مع حلقة الـ Pipeline Manager (protein_id -> motif_info)
    motif_results = {}
    for entry in detected_motifs:
        p_name = entry["protein_name"]
        # إذا تكرر ارتباط البروتين في أكثر من موقع، نأخذ القيمة الأعلى أو نسجل الموقع الأول
        if p_name not in motif_results:
            # ملاحظة: is_missing ما بتتحدد هون — الدالة هاي بتشتغل على تسلسل
            # واحد بس (مريض أو سليم) فمفيش عندها مرجع تقارن فيه. المقارنة
            # الفعلية (مريض مقابل سليم) صايرة بـ pipeline_manager._step_motifs
            # عبر مناداة هاي الدالة مرتين ثم مقارنة النتيجتين.
            motif_results[p_name] = {
                "position_index": entry["position"],
                "strand": entry["strand"],
                "delta_score": entry["score"],
            }
            
    return motif_results


def fetch_pdb_file(protein_name: str) -> str:
    """
    يجلب ملف الـ PDB للبروتين، ويقوم بنسخه أو حفظه مباشرة داخل مجلد الـ Media الخاص بدجانغو
    لكي يسهل على الـ Front-end الوصول إليه عبر رابط URL، ويعيد المسار النسبي.
    """
    # تحديد مجلد الحفظ داخل الـ Media الخاص بدجانغو
    relative_folder = 'genomics/pdb_structures/'
    absolute_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(absolute_folder, exist_ok=True)

    # إنشاء الـ Fetcher وتوجيه الكاش الخاص به مباشرة إلى مجلد ميديا دجانغو
    fetcher = ProteinStructureFetcher(cache_dir=absolute_folder)
    
    # جلب وتحميل الملف (سيعيد المسار المطلق للملف المحفوظ في الميديا)
    absolute_pdb_path = fetcher.fetch(protein_name)
    
    # استخراج اسم الملف النهائي فقط لإرجاع المسار النسبي لقاعدة البيانات
    filename = os.path.basename(absolute_pdb_path)
    return os.path.join(relative_folder, filename)


def calculate_spatial_docking(pdb_relative_path: str, motif_info: dict) -> dict:
    """
    يأخذ ملف الـ PDB ومعلومات الموقع الجيني، ويحسب مصفوفات الدوران والإزاحة (Translation & Rotation)
    لتثبيت ذرات البروتين بدقة ثلاثية الأبعاد فوق خيط الـ DNA.
    """
    position_index = motif_info.get("position_index", 0)
    
    # هنا ستوضع معادلات التحويل الرياضية وربطها بالـ 3D Coords لاحقاً
    # حالياً نرجع هيكل رياضي افتراضي متزن وجاهز للاستقبال في الواجهات
    return {
        "position": [float(position_index * 0.34), 0.0, 0.0],  # مثال لحساب الإزاحة بناءً على المسافة بين القواعد
        "rotation": [0.0, 90.0, 0.0]  # زوايا الدوران الافتراضية للتركيب الفراغي
    }