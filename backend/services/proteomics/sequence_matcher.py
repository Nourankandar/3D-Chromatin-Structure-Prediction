"""
services/proteomics/sequence_matcher.py

يأخذ تسلسل أحماض أمينية (ناتج من translator.py) ويحاول مطابقته مع
بروتينات معروفة عبر EBI BLAST REST API (NCBI BLAST غير متاح كـ REST مباشر
بنفس الكفاءة، وEBI يوفر واجهة مكافئة ومجانية).

هذه العملية غير حتمية بمعنى الشبكة (تعتمد على استجابة API خارجي)
لكنها ليست AI - هي محرك alignment إحصائي كلاسيكي (BLAST algorithm).
"""

import time
import requests
from typing import Optional, TypedDict

from rcsb_lookup import get_pdb_ids_for_uniprot
from .structure_fetcher import build_direct_cdn_url

EBI_BLAST_BASE = "https://www.ebi.ac.uk/Tools/services/rest/ncbiblast"
IDENTITY_THRESHOLD = 80.0  # % - أقل من هيك ما بنعتبره match مقنع
POLL_INTERVAL_SECONDS = 3
MAX_POLL_ATTEMPTS = 20  # ~60 ثانية كحد أقصى انتظار


class MatchResult(TypedDict):
    matched_protein_name: str
    matched_uniprot_id: str
    matched_pdb_id: Optional[str]
    matched_pdb_cdn_url: Optional[str]
    match_identity_percent: float
    is_match_found: bool


def _submit_blast_job(amino_acid_sequence: str) -> Optional[str]:
    """يرسل مهمة BLAST جديدة لـ EBI ويرجع job_id، أو None عند الفشل."""
    try:
        response = requests.post(
            f"{EBI_BLAST_BASE}/run",
            data={
                "email": "genomics-pipeline@yourdomain.com",  # مطلوب من EBI
                "program": "blastp",
                "database": "uniprotkb_swissprot",
                "stype": "protein",
                "sequence": amino_acid_sequence,
            },
            timeout=20,
        )
        if response.status_code == 200:
            return response.text.strip()  # الـ job_id يرجع كنص خام
    except requests.RequestException:
        pass
    return None


def _poll_job_status(job_id: str) -> bool:
    """ينتظر حتى تنتهي مهمة BLAST. يرجع True لو انتهت بنجاح (FINISHED)."""
    for _ in range(MAX_POLL_ATTEMPTS):
        try:
            response = requests.get(f"{EBI_BLAST_BASE}/status/{job_id}", timeout=15)
            status = response.text.strip()
            if status == "FINISHED":
                return True
            if status in ("FAILURE", "ERROR", "NOT_FOUND"):
                return False
        except requests.RequestException:
            pass
        time.sleep(POLL_INTERVAL_SECONDS)
    return False  # timeout


def _fetch_best_hit(job_id: str) -> Optional[dict]:
    """
    يجلب نتائج المهمة بصيغة JSON، ويرجع أفضل hit (الأعلى identity/score).
    """
    try:
        response = requests.get(
            f"{EBI_BLAST_BASE}/result/{job_id}/json", timeout=20
        )
        if response.status_code != 200:
            return None

        data = response.json()
        hits = data.get("hits", [])
        if not hits:
            return None

        best_hit = hits[0]  # النتائج تأتي مرتبة تنازلياً حسب bit score افتراضياً
        best_alignment = best_hit["hit_hsps"][0]

        return {
            "uniprot_id": best_hit["hit_acc"],
            "protein_name": best_hit.get("hit_desc", best_hit["hit_acc"]),
            "identity_percent": float(best_alignment["hsp_identity"]),
        }
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None


def find_matching_protein(amino_acid_sequence: str) -> Optional[MatchResult]:
    """
    يحاول إيجاد بروتين معروف يطابق تسلسل الأحماض الأمينية المعطى.

    Returns:
        MatchResult عند وجود تطابق مقنع (>= IDENTITY_THRESHOLD),
        أو None عند عدم وجود تطابق كافٍ أو فشل الاتصال بالـ API
        (وفي الحالتين، يجب على pipeline_manager تفعيل ESMFold كـ fallback).
    """
    if not amino_acid_sequence or len(amino_acid_sequence) < 10:
        # سلسلة قصيرة جداً لا معنى لعمل BLAST عليها
        return None

    job_id = _submit_blast_job(amino_acid_sequence)
    if not job_id:
        return None

    if not _poll_job_status(job_id):
        return None

    best_hit = _fetch_best_hit(job_id)
    if not best_hit:
        return None

    if best_hit["identity_percent"] < IDENTITY_THRESHOLD:
        return None

    pdb_ids = get_pdb_ids_for_uniprot(best_hit["uniprot_id"])
    matched_pdb_id = pdb_ids[0] if pdb_ids else None
    # الرابط لا يُبنى إلا لو فعلاً عندنا pdb_id مؤكد الوجود من RCSB نفسه
    matched_pdb_cdn_url = (
        build_direct_cdn_url(matched_pdb_id) if matched_pdb_id else None
    )

    return {
        "matched_protein_name": best_hit["protein_name"],
        "matched_uniprot_id": best_hit["uniprot_id"],
        "matched_pdb_id": matched_pdb_id,
        "matched_pdb_cdn_url": matched_pdb_cdn_url,
        "match_identity_percent": round(best_hit["identity_percent"], 2),
        "is_match_found": True,
    }