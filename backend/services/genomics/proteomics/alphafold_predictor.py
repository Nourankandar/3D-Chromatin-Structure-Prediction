"""
services/genomics/proteomics/alphafold_predictor.py
====================================================================
الخطوة 6: التنبؤ ببنية البروتين ثلاثية الأبعاد عبر AlphaFold API (أونلاين).

بيتفعّل بس لو في فرق فعلي غير silent بين بروتين المريض والسليم — ما في
داعي نبعت طلب API لبروتين مطابق 100% للمرجع.

ملاحظة: هاد API خارجي (أونلاين) بموافقة المركز — الهدف تعليمي بالمرحلة
الحالية، مو نشر سريري نهائي.
====================================================================
"""

import logging
import os
import time
from typing import Optional, TypedDict

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# AlphaFold DB (EBI) بيغطي بس البروتينات المعروفة/المودَّلة مسبقاً
# (UniProt entries). للبروتينات الطافرة (patient variant) ما رح تلاقيها
# جاهزة أصلاً — لازم نموذج تنبؤ حي (ESMFold API المجاني، أسرع وأخف من
# تشغيل AlphaFold محلياً، ومناسب تماماً للمرحلة التعليمية الحالية).
# ─────────────────────────────────────────────────────────────────
ESMFOLD_API_URL = "https://api.esmatlas.com/foldSequence/v1/pdb/"
ALPHAFOLD_DB_API_URL = "https://alphafold.ebi.ac.uk/api/prediction/"

REQUEST_TIMEOUT_SECONDS = 120
MAX_RETRIES = 2


class StructurePredictionError(Exception):
    """يُرفع عند فشل الحصول على بنية 3D من أي مصدر (DB أو تنبؤ حي)."""


class StructureResult(TypedDict):
    source: str              # "alphafold_db" | "esmfold_predicted"
    pdb_relative_path: str
    uniprot_accession: Optional[str]
    confidence_note: str


def _fetch_alphafold_db_structure(uniprot_accession: str) -> Optional[str]:
    """
    يحاول يجيب بنية جاهزة مسبقاً من AlphaFold DB (لو البروتين معروف
    ومطابق 100% لإدخال UniProt — بيصير هاد بس بحالة السليم عادة، أو
    مريض بدون طفرة فعلية بهاد الجين).
    """
    try:
        response = requests.get(
            f"{ALPHAFOLD_DB_API_URL}{uniprot_accession}",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if not data:
            return None
        return data[0].get("pdbUrl")
    except (requests.RequestException, ValueError, IndexError, KeyError) as exc:
        logger.warning("[AlphaFold] فشل جلب بنية جاهزة لـ %s: %s", uniprot_accession, exc)
        return None


def _predict_structure_esmfold(amino_acid_sequence: str) -> str:
    """
    يبعت تسلسل الأحماض الأمينية (يلي فيه الطفرة، غير موجود بأي داتابيز
    جاهزة) لـ ESMFold API، وبيرجع محتوى ملف PDB كنص خام.

    ESMFold محدود لتسلسلات لغاية ~400 حمض أميني تقريباً بالنسخة المجانية —
    كافي لمعظم البروتينات البشرية القصيرة/المتوسطة (زي HBB بـ146).
    """
    if len(amino_acid_sequence) > 400:
        raise StructurePredictionError(
            f"تسلسل طويل جداً ({len(amino_acid_sequence)} حمض أميني) — "
            f"ESMFold المجاني بيدعم لغاية ~400 حمض أميني بس."
        )

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                ESMFOLD_API_URL,
                data=amino_acid_sequence,
                timeout=REQUEST_TIMEOUT_SECONDS,
                headers={"Content-Type": "text/plain"},
            )
            response.raise_for_status()
            pdb_text = response.text
            if not pdb_text.strip().startswith(("ATOM", "HEADER", "REMARK")):
                raise StructurePredictionError("استجابة ESMFold غير صالحة (مش ملف PDB).")
            return pdb_text
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning(
                "[AlphaFold/ESMFold] محاولة %d/%d فشلت: %s", attempt, MAX_RETRIES, exc
            )
            if attempt < MAX_RETRIES:
                time.sleep(3)

    raise StructurePredictionError(f"فشل التنبؤ ببنية البروتين بعد {MAX_RETRIES} محاولات: {last_exc}")


def predict_protein_structure(
    amino_acid_sequence: str,
    output_name_hint: str,
    uniprot_accession: Optional[str] = None,
    mutation_type: str = "unknown",
) -> StructureResult:
    """
    الجسر الرئيسي المستدعى من pipeline_manager للخطوة 6.

    المنطق:
      1) لو mutation_type == "none" أو "silent" و uniprot_accession متوفر:
         نحاول أول شي AlphaFold DB (بنية جاهزة مسبقاً، أسرع وأدق —
         مافي داعي نموذج تنبؤ حي لبروتين مطابق للمرجع).
      2) غير هيك (فيه طفرة فعلية missense/nonsense/frameshift، أو ما في
         uniprot_accession): لازم تنبؤ حي عبر ESMFold — لأنه التسلسل
         الطافر مش موجود بأي داتابيز مسبقاً بطبيعة الحال.
    """
    pdb_text: Optional[str] = None
    source = "esmfold_predicted"

    if mutation_type in ("none", "silent") and uniprot_accession:
        db_url = _fetch_alphafold_db_structure(uniprot_accession)
        if db_url:
            try:
                pdb_response = requests.get(db_url, timeout=REQUEST_TIMEOUT_SECONDS)
                pdb_response.raise_for_status()
                pdb_text = pdb_response.text
                source = "alphafold_db"
            except requests.RequestException as exc:
                logger.warning("[AlphaFold] فشل تحميل ملف PDB الجاهز: %s — رح نتنبأ حي بدالو", exc)

    if pdb_text is None:
        logger.info(
            "[AlphaFold] تنبؤ حي عبر ESMFold لـ %s (mutation_type=%s، %d حمض أميني)",
            output_name_hint, mutation_type, len(amino_acid_sequence),
        )
        pdb_text = _predict_structure_esmfold(amino_acid_sequence)

    relative_folder = "genomics/protein_structures/pdb/"
    absolute_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(absolute_folder, exist_ok=True)

    output_filename = f"{output_name_hint}_structure.pdb"
    absolute_output_path = os.path.join(absolute_folder, output_filename)

    with open(absolute_output_path, "w") as f:
        f.write(pdb_text)

    confidence_note = (
        "بنية مأخوذة من AlphaFold DB (عالية الثقة، بروتين معروف مسبقاً)."
        if source == "alphafold_db"
        else "بنية متنبّأ بها حياً عبر ESMFold (تقريبية — البروتين يحتوي طفرة غير موثقة مسبقاً)."
    )

    logger.info("[AlphaFold] تم حفظ البنية: %s (source=%s)", absolute_output_path, source)

    return {
        "source": source,
        "pdb_relative_path": os.path.join(relative_folder, output_filename),
        "uniprot_accession": uniprot_accession,
        "confidence_note": confidence_note,
    }