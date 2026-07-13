"""
test_protein_pipeline.py
--------------------------------------------------------------------
سكريبت تجريبي مستقل (بدون Django) لاختبار:
  1) protein_search.search_protein_by_gene  -> تحويل اسم الجين لـ UniProt ID + PDB IDs
  2) protein_fetcher.ProteinStructureFetcher.fetch -> تنزيل ملف PDB فعلي
     (أو AlphaFold كـ fallback لو ما في هيكل تجريبي)

شغّله مباشرة:
    python test_protein_pipeline.py

بيحفظ الملفات بمجلد محلي test_pdb_cache/ مشان ما يخربط بكاش المشروع الأساسي.
--------------------------------------------------------------------
"""

import os
import sys

# ------------------------------------------------------------------
# الملفين مش بنفس المجلد بمشروعك الحقيقي:
#   - protein_fetcher.py  -> ai_engine/models/Proteins/ProteinStructures/
#   - protein_search.py   -> backend/services/scanning_motifs/
#
# عدّل السطرين تحت ليطابقو مسار مشروعك الفعلي على جهازك (حط المسار
# المطلق أو النسبي لمجلد ai_engine ومجلد backend/services انطلاقاً من
# مكان تشغيل هاد السكريبت).
# ------------------------------------------------------------------
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.services.scanning_motifs.protein_search import search_protein_by_gene
from ai_engine.models.Proteins.ProteinStructures.protein_fetcher import ProteinStructureFetcher


# جينات للتجربة - خليطة من بروتينات معروفة (بعضها إله PDB تجريبي، بعضها لأ)
TEST_GENES = ["CTCF", "TP53", "BRCA1", "GATA1"]

TEST_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_pdb_cache")


def test_gene_search():
    print("=" * 70)
    print("TEST 1: البحث عن الجينات بـ UniProt + RCSB PDB (بدون تنزيل)")
    print("=" * 70)

    results = {}
    for gene in TEST_GENES:
        print(f"\n--> البحث عن الجين: {gene}")
        result = search_protein_by_gene(gene)
        if result is None:
            print(f"    [✗] ما لقيتش نتيجة لـ {gene}")
            continue

        print(f"    [✓] UniProt ID  : {result['uniprot_id']}")
        print(f"    [✓] Protein name: {result['protein_name']}")
        print(f"    [✓] PDB IDs     : {result['pdb_ids'] or '(ما في هياكل تجريبية، رح يستخدم AlphaFold)'}")
        results[gene] = result

    return results


def test_pdb_download(gene_results: dict):
    print("\n" + "=" * 70)
    print("TEST 2: تنزيل ملف PDB الفعلي (أو AlphaFold) لكل جين")
    print("=" * 70)

    fetcher = ProteinStructureFetcher(cache_dir=TEST_CACHE_DIR)

    for gene in gene_results:
        print(f"\n--> تنزيل هيكل {gene}...")
        try:
            path = fetcher.fetch(gene)
            exists = os.path.exists(path)
            size_kb = os.path.getsize(path) / 1024 if exists else 0
            print(f"    [✓] تم الحفظ: {path}")
            print(f"    [✓] الملف موجود فعلياً: {exists} | الحجم: {size_kb:.1f} KB")
        except Exception as e:
            print(f"    [✗] فشل تنزيل {gene}: {e}")


def test_unknown_gene():
    # جين غير موجود مشان نتأكد إن الكود بيرجع None ومش بيطيح
    print("\n" + "=" * 70)
    print("TEST 3: جين غير موجود (للتأكد من الـ error handling)")
    print("=" * 70)

    fake_gene = "NOTAREALGENE123"
    result = search_protein_by_gene(fake_gene)
    print(f"نتيجة البحث عن '{fake_gene}': {result}")
    assert result is None, "المفروض يرجع None لجين مش موجود!"
    print("[✓] تصرف صحيح - رجع None زي المتوقع")


if __name__ == "__main__":
    gene_results = test_gene_search()
    if gene_results:
        test_pdb_download(gene_results)
    test_unknown_gene()

    print("\n" + "=" * 70)
    print(f"خلصت الاختبارات. الملفات المنزّلة (لو في) موجودة بـ: {TEST_CACHE_DIR}")
    print("=" * 70)