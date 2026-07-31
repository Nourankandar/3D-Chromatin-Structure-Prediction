"""
services/proteomics/structure_fetcher.py

قرار معماري: لا نخزن ملفات PDB على هاردسك السيرفر إطلاقاً.
الفرونت إند (3Dmol.js / Mol*) يرسم البنية مباشرة من CDN الخاص بـ RCSB.

ملاحظة مهمة: لا حاجة للتحقق (validation) من صحة الـ PDB ID هنا، لأن أي
pdb_id يصل لهذا الملف يكون أصلاً طالعاً من استعلام RCSB نفسه
(عبر shared/rcsb_lookup.get_pdb_ids_for_uniprot) - أي أنه متحقق منه
ضمنياً ومضمون الوجود. الباك إند لا يرسل للفرونت إلا أسماء/معرّفات مؤكدة.

مسؤولية هذا الملف الآن محصورة بشيئين فقط:
1. تجهيز الرابط المباشر (CDN URL) ليستخدمه الفرونت إند للرسم.
2. جلب محتوى الملف كـ string في الذاكرة (RAM) فقط، عند الحاجة لتحليل حسابي
   داخلي في الباك إند - بدون أي كتابة على القرص.
"""

import requests
from typing import Optional

RCSB_FILES_BASE = "https://files.rcsb.org/download"


def build_direct_cdn_url(pdb_id: str, file_format: str = "pdb") -> str:
    """
    يبني الرابط المباشر (CDN URL) الذي يستخدمه الفرونت إند مباشرة
    (مثلاً في 3Dmol.js: $3Dmol.download("url:" + direct_cdn_url, viewer)).

    file_format:
        "pdb" -> https://files.rcsb.org/download/1TRZ.pdb
        "cif" -> https://files.rcsb.org/download/1TRZ.cif
    """
    pdb_id_clean = pdb_id.strip().upper()
    extension = "cif" if file_format == "cif" else "pdb"
    return f"{RCSB_FILES_BASE}/{pdb_id_clean}.{extension}"


def fetch_structure_as_string(pdb_id: str) -> Optional[str]:
    """
    يجلب محتوى ملف الـ PDB كنص كامل في الذاكرة (RAM) فقط - بدون أي كتابة
    على القرص. يُستخدم فقط عند الحاجة لتحليل حسابي داخلي بالباك إند
    (مثل حساب مسافات ذرية أو تمرير الإحداثيات لموديل آخر مثل ESMFold
    للمقارنة). لا علاقة له بمسار الفرونت إند إطلاقاً.

    Returns:
        محتوى الملف كـ string، أو None عند فشل الجلب (نادر، لأن الـ pdb_id
        مؤكد الوجود أصلاً، لكن ممكن يصير timeout أو مشكلة شبكة مؤقتة).
    """
    url = build_direct_cdn_url(pdb_id, file_format="pdb")

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.text
    except requests.RequestException:
        pass

    return None