
# backend/services/scanning_motifs/scanner.py

import os
import logging
import numpy as np
from django.conf import settings

# استدعاء المحركات الحسابية من الـ ai_engine المستقل
from ai_engine.models.Proteins.MotifScanner.protein_lookup import GenomicMotifScanner
from ai_engine.models.Proteins.ProteinStructures.protein_fetcher import ProteinStructureFetcher

import numpy as np
from core.utils.genomics_utils import call_dnase_peaks, is_position_in_peaks

logger = logging.getLogger(__name__)

def run_motif_delta_analysis(fasta_absolute_path: str, dnase_signal: np.ndarray = None) -> dict:
    """
    يقرأ ملف الـ FASTA، ويشغل الـ Motif Scanner لاستخراج البروتينات المتأثرة.
    لو انبعتت dnase_signal، منفلتر الـ motifs بحيث نحتفظ بس باللي واقعة جوا
    مناطق الانفتاح (DNase peaks) — لأنه بروتين ما إلو معنى بيولوجي يرتبط
    بمنطقة كروماتين مقفولة أصلاً.
    """
    with open(fasta_absolute_path, "r") as f:
        lines = f.readlines()
    dna_sequence = "".join(line.strip() for line in lines if not line.startswith(">"))

    scanner = GenomicMotifScanner()
    detected_motifs = scanner.scan_sequence(dna_sequence, threshold=0.8)

    # ── فلترة حسب DNase peaks (لو متوفرة) ──────────────────────────
    peaks = []
    if dnase_signal is not None:
        peaks = call_dnase_peaks(dnase_signal, min_fraction_of_max=0.5, min_peak_width=10)
        if not peaks:
            logger.warning(
                "[Scanner] لا توجد مناطق انفتاح (DNase peaks) بهاي المنطقة — "
                "بيولوجياً هاد يعني كروماتين مقفول بالكامل، فمافي أي بروتين متوقع يرتبط هون."
            )
            return {}   # نرجع فاضي — مفيش داعي نفحص أي بروتين أصلاً
        logger.info("[Scanner] تم تحديد %d منطقة انفتاح (DNase peaks)", len(peaks))
    motif_results = {}
    skipped_by_dnase = 0

    for entry in detected_motifs:
        position = entry["position"]

        if peaks and not is_position_in_peaks(position, peaks):
            skipped_by_dnase += 1
            continue  # الموقع خارج أي منطقة مفتوحة — نتجاهله

        key = entry["jaspar_id"]
        if key not in motif_results:
            motif_results[key] = {
                "protein_name": entry["protein_name"],
                "jaspar_id": entry["jaspar_id"],
                "position_index": position,
                "strand": entry["strand"],
                "delta_score": entry["score"],
            }

    if peaks:
        logger.info(
            "[Scanner] %d motif تم تجاهلها لوقوعها خارج مناطق الانفتاح، %d تبقى",
            skipped_by_dnase, len(motif_results),
        )

    return motif_results

def fetch_pdb_file(protein_name: str) -> str:
    """
    يجلب ملف الـ PDB للبروتين، ويقوم بنسخه أو حفظه مباشرة داخل مجلد الـ Media الخاص بدجانغو
    لكي يسهل على الـ Front-end الوصول إليه عبر رابط URL، ويعيد المسار النسبي.

    ملاحظة: هاد بياخد اسم الجين (protein_name) مش jaspar_id، لأنه
    ProteinStructureFetcher بيعمل بحث بـ UniProt عن طريق اسم الجين.

    بعض motifs بـ JASPAR بتكون لـ "complex" من بروتينين سوا (زي "HOXD12::ELK1")
    — UniProt ما بيفهم هيك صيغة، فمنفصل ومنستخدم بس أول بروتين بالمركّب.
    """
    if "::" in protein_name:
        original_name = protein_name
        protein_name = protein_name.split("::")[0].strip()
        # (اختياري) تسجيل تنويه بسيط بدل ما ينكتم تماماً
        import logging
        logging.getLogger(__name__).info(
            "[PDB Fetch] '%s' هو بروتين مركّب (heterodimer) — استخدمنا '%s' فقط لجلب البنية",
            original_name, protein_name,
        )

    relative_folder = 'genomics/pdb_structures/'
    absolute_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(absolute_folder, exist_ok=True)

    fetcher = ProteinStructureFetcher(cache_dir=absolute_folder)
    absolute_pdb_path = fetcher.fetch(protein_name)

    filename = os.path.basename(absolute_pdb_path)
    return os.path.join(relative_folder, filename)

def calculate_spatial_docking(coords_raw: list, position_index, resolution: int = 5000) -> dict | None:
    """
    يلاقي أقرب نقطة 3D (bin) لموقع البروتين على المحور الجيني،
    بدون أي حاجة لملف PDB.
    """
    if not coords_raw or position_index is None:
        return None

    target_bin = int(position_index) // resolution
    if target_bin >= len(coords_raw):
        target_bin = len(coords_raw) - 1
    if target_bin < 0:
        return None

    point = coords_raw[target_bin]
    return {"x": point["x"], "y": point["y"], "z": point["z"]}