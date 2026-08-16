"""
services/proteomics/gtf_index.py
====================================================================
فهرسة ملف GENCODE GTF (مضغوط .gz) مرة واحدة عند أول استخدام، وتخزين
فهرس خفيف (pickle) على القرص لتسريع الاستعلامات اللاحقة — لأنه فتح
وتحليل ملف GTF كامل (مئات الآلاف من السطور) في كل تشغيلة مكلف جداً.

الإحداثيات في GTF نفسها هي 1-based inclusive (المعيار القياسي)، بينما
باقي المشروع (locator, fetcher) يعتمد نظام 0-based half-open (نفس
منطق Python slicing). كل التحويلات تتم هنا مرة واحدة عند بناء الفهرس.
====================================================================
"""

import gzip
import logging
import os
import pickle
import re
from typing import Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)

_ATTR_PATTERN = re.compile(r'(\w+)\s+"([^"]*)"')


class ExonInfo(TypedDict):
    start: int  # 0-based, جينومي
    end: int    # 0-based exclusive, جينومي


class TranscriptInfo(TypedDict):
    transcript_id: str
    tags: List[str]
    exons: List[ExonInfo]           # مرتبة تصاعدياً حسب الموقع الجينومي دائماً
    cds_start: Optional[int]        # 0-based
    cds_end: Optional[int]          # 0-based exclusive


class GeneInfo(TypedDict):
    gene_id: str
    gene_name: str
    chromosome: str
    strand: str
    start: int
    end: int
    transcripts: Dict[str, TranscriptInfo]


def _parse_attributes(attr_field: str) -> Dict[str, str]:
    """
    يحول عمود الـ attributes (العمود التاسع بالـ GTF) لقاموس.
    مثال: 'gene_id "ENSG00000244734.4"; gene_name "HBB"; tag "MANE_Select";'
    ملاحظة: GTF ممكن يكرر tag أكتر من مرة بنفس السطر، فبنجمعهم بمفتاح
    خاص "tag_list".
    """
    attrs: Dict[str, str] = {}
    tags: List[str] = []
    for key, value in _ATTR_PATTERN.findall(attr_field):
        if key == "tag":
            tags.append(value)
        else:
            attrs[key] = value
    if tags:
        attrs["tag_list"] = ",".join(tags)
    return attrs


def build_gtf_index(gtf_gz_path: str, cache_path: str) -> Dict[str, List[GeneInfo]]:
    """
    يبني فهرس الجينات من ملف GTF مضغوط، ويخزنه كـ pickle على القرص.
    لو الفهرس المخزن موجود أصلاً وأحدث من ملف الـ GTF الأصلي، بيرجعه
    مباشرة بدون إعادة تحليل الملف الكامل.
    """
    if os.path.exists(cache_path) and os.path.getmtime(cache_path) >= os.path.getmtime(gtf_gz_path):
        logger.info("[GTF Index] تحميل الفهرس المخزّن من: %s", cache_path)
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    logger.info("[GTF Index] بناء فهرس جديد من: %s (قد يستغرق دقيقة أو دقيقتين)", gtf_gz_path)

    genes_by_chrom: Dict[str, Dict[str, GeneInfo]] = {}

    with gzip.open(gtf_gz_path, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue

            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9:
                continue

            chrom, _source, feature, start1, end1, _score, strand, _frame, attr_field = fields

            if feature not in ("gene", "transcript", "exon", "CDS", "stop_codon"):
                continue

            attrs = _parse_attributes(attr_field)
            start0 = int(start1) - 1   # تحويل 1-based -> 0-based
            end0 = int(end1)           # النهاية الـ inclusive بـ GTF == exclusive بـ Python تلقائياً

            if feature == "gene":
                gene_id = attrs.get("gene_id")
                if not gene_id:
                    continue
                genes_by_chrom.setdefault(chrom, {})[gene_id] = {
                    "gene_id": gene_id,
                    "gene_name": attrs.get("gene_name", gene_id),
                    "chromosome": chrom,
                    "strand": strand,
                    "start": start0,
                    "end": end0,
                    "transcripts": {},
                }

            elif feature == "transcript":
                gene_id = attrs.get("gene_id")
                transcript_id = attrs.get("transcript_id")
                if not gene_id or not transcript_id:
                    continue
                gene = genes_by_chrom.setdefault(chrom, {}).setdefault(gene_id, {
                    "gene_id": gene_id,
                    "gene_name": attrs.get("gene_name", gene_id),
                    "chromosome": chrom,
                    "strand": strand,
                    "start": start0,
                    "end": end0,
                    "transcripts": {},
                })
                tag_list = attrs.get("tag_list", "")
                gene["transcripts"][transcript_id] = {
                    "transcript_id": transcript_id,
                    "tags": tag_list.split(",") if tag_list else [],
                    "exons": [],
                    "cds_start": None,
                    "cds_end": None,
                }

            elif feature == "exon":
                gene_id = attrs.get("gene_id")
                transcript_id = attrs.get("transcript_id")
                if not gene_id or not transcript_id:
                    continue
                gene = genes_by_chrom.get(chrom, {}).get(gene_id)
                if gene is None:
                    continue
                transcript = gene["transcripts"].get(transcript_id)
                if transcript is None:
                    continue
                transcript["exons"].append({"start": start0, "end": end0})

            elif feature == "CDS":
                gene_id = attrs.get("gene_id")
                transcript_id = attrs.get("transcript_id")
                if not gene_id or not transcript_id:
                    continue
                gene = genes_by_chrom.get(chrom, {}).get(gene_id)
                if gene is None:
                    continue
                transcript = gene["transcripts"].get(transcript_id)
                if transcript is None:
                    continue
                # نجمع أصغر بداية وأكبر نهاية بين كل سطور CDS لنفس الـ transcript
                # (الـ CDS ممكن يكون موزع على أكتر من إكسون، فبيجي أكتر من سطر)
                if transcript["cds_start"] is None or start0 < transcript["cds_start"]:
                    transcript["cds_start"] = start0
                if transcript["cds_end"] is None or end0 > transcript["cds_end"]:
                    transcript["cds_end"] = end0

            elif feature == "stop_codon":
                gene_id = attrs.get("gene_id")
                transcript_id = attrs.get("transcript_id")
                if not gene_id or not transcript_id:
                    continue
                gene = genes_by_chrom.get(chrom, {}).get(gene_id)
                if gene is None:
                    continue
                transcript = gene["transcripts"].get(transcript_id)
                if transcript is None:
                    continue
                
                if transcript["cds_start"] is None or start0 < transcript["cds_start"]:
                    transcript["cds_start"] = start0
                if transcript["cds_end"] is None or end0 > transcript["cds_end"]:
                    transcript["cds_end"] = end0

    # ترتيب الإكسونات حسب الموقع الجينومي (تصاعدي) لكل transcript
    result: Dict[str, List[GeneInfo]] = {}
    for chrom, genes in genes_by_chrom.items():
        gene_list = []
        for gene in genes.values():
            for transcript in gene["transcripts"].values():
                transcript["exons"].sort(key=lambda e: e["start"])
            gene_list.append(gene)
        gene_list.sort(key=lambda g: g["start"])
        result[chrom] = gene_list

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(result, f)

    logger.info("[GTF Index] تم بناء الفهرس وتخزينه: %s (%d كروموسوم)", cache_path, len(result))
    return result


def find_genes_in_region(index: Dict[str, List[GeneInfo]], chromosome: str, start: int, end: int) -> List[GeneInfo]:
    """
    يرجع كل الجينات (بحدودها الجينية الكاملة، مش نافذة البحث) اللي
    بتتقاطع مع المدى (start, end) — نظام 0-based half-open.
    """
    genes = index.get(chromosome, [])
    return [g for g in genes if g["start"] < end and g["end"] > start]


def select_representative_transcript(gene: GeneInfo) -> Optional[TranscriptInfo]:
    """
    يختار الـ transcript الممثل الرسمي للجين وفق الأولوية التالية:
      1) MANE_Select (المعتمد سريرياً من NCBI+Ensembl سوا — الأدق والأوثق)
      2) Ensembl_canonical (احتياطي، عادة لجينات على كروموسومات بديلة)
      3) الأطول من ناحية طول الـ CDS (احتياطي أخير لو مافي تصنيف رسمي)
    يرجع None لو الجين مالوش أي transcript فيه CDS كامل (مثلاً non-coding gene).
    """
    candidates = [
        t for t in gene["transcripts"].values()
        if t["cds_start"] is not None and t["cds_end"] is not None and t["exons"]
    ]
    if not candidates:
        return None

    for t in candidates:
        if "MANE_Select" in t["tags"]:
            return t
    for t in candidates:
        if "Ensembl_canonical" in t["tags"]:
            return t

    def cds_length(t: TranscriptInfo) -> int:
        return t["cds_end"] - t["cds_start"]

    return max(candidates, key=cds_length)