# services/DNASE/predictor.py
import os
import numpy as np
from django.conf import settings

# استدعاء دالة التنبؤ الحقيقية من الـ ai_engine المستقل تماماً
from ai_engine.models.Dnase.DNASEpredictor import predict_dnase_accessibility

def read_fasta_file(file_path: str) -> str:
    """
    يقرأ ملف الـ FASTA الحقيقي من القرص ويستخرج منه تسلسل الـ DNA النظيف كـ string
    """
    with open(file_path, "r") as f:
        lines = f.readlines()
    
    sequence = "".join(line.strip() for line in lines if not line.startswith(">"))
    return sequence

def predict_dnase_profiles(fasta_absolute_path: str, basset_track_id: int) -> str:
    """
    الجسر المركزي الذي يستدعيه الـ Pipeline Manager:
    يقرأ الملف، يشغل موديل Basset، ويحفظ مصفوفة التنبؤ على القرص ويعيد المسار النسبي.
    """
    # 1. تحويل ملف الـ FASTA المرفوع إلى سلسلة نصية يفهمها الموديل
    raw_dna_sequence = read_fasta_file(fasta_absolute_path)
    
    # 2. استدعاء دالتكِ الحسابية وتمرير الإعدادات الذكية التي صممتيها
    results = predict_dnase_accessibility(
        sequence=raw_dna_sequence,
        model=None,         # سيقوم الـ model_loader الخاص بكِ بشحنه تلقائياً بداخل الدالة
        step=50,            # أعلى دقة للتداخل بين النوافذ
        batch_size=16,      # حجم دفعة متزن ومستقر للـ RAM وكارت الشاشة
        smooth_sigma=30.0   # التنعيم الغاوسي المعتمد لديكِ
    )
    
  
    scores_matrix = results['scores_164']
    
    track_index = min(max(0, basset_track_id), 163) if basset_track_id is not None else 0
    target_cell_scores = scores_matrix[:, track_index]
    
    base_name = os.path.basename(fasta_absolute_path).split('.')[0]
    output_filename = f"{base_name}_track_{track_index}_dnase.npy"
    
    relative_folder = 'genomics/raw_inputs/dnas_signals/'
    absolute_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(absolute_folder, exist_ok=True)
    
    absolute_file_path = os.path.join(absolute_folder, output_filename)
    
    np.save(absolute_file_path, target_cell_scores)
    
    return os.path.join(relative_folder, output_filename)