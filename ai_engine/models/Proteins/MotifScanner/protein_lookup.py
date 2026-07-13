# MotifScanner/protein_lookup.py
import os
from Bio import motifs
from Bio.Seq import Seq

class GenomicMotifScanner:
    def __init__(self, jaspar_file_path=None):
        if jaspar_file_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.jaspar_file_path = os.path.join(current_dir, "JASPAR2022_CORE_vertebrates.jaspar")
        else:
            self.jaspar_file_path = jaspar_file_path
            
        self.motifs_database = []
        self._load_local_motifs()

    def _load_local_motifs(self):
        if not os.path.exists(self.jaspar_file_path):
            raise FileNotFoundError(f"ملف قاعدة البيانات JASPAR غير موجود في المسار: {self.jaspar_file_path}")
        with open(self.jaspar_file_path) as f:
            self.motifs_database = list(motifs.parse(f, "jaspar"))

    def scan_sequence(self, dna_sequence, threshold=0.8):
        seq_obj = Seq(dna_sequence.upper())
        detected = []

        for motif in self.motifs_database:
            # استخدام حساب الاحتمالات اللوغاريتمية القياسي
            pssm = motif.counts.normalize(pseudocounts=0.5).log_odds()
            
            min_score = pssm.min
            max_score = pssm.max
            motif_threshold = min_score + threshold * (max_score - min_score)

            # دالة البحث تعود بالموقع والمجموع (Score)
            for position, score in pssm.search(seq_obj, threshold=motif_threshold):
                # التعامل مع الـ Strand العكسي وحساب موقعه بشكل دقيق وآمن بيولوجياً
                if position >= 0:
                    strand = "+"
                    actual_pos = position
                else:
                    strand = "-"
                    actual_pos = len(dna_sequence) + position # دمج الموقع السالب مع طول السلسلة

                detected.append({
                    "protein_name": motif.name,    
                    "jaspar_id":    motif.matrix_id,
                    "position":     actual_pos,
                    "strand":       strand,
                    "score":        round(float(score), 2)
                })
        return detected