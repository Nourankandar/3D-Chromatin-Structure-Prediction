"""
services/proteomics/shared/rcsb_lookup.py

دالة مشتركة: uniprot_id -> قائمة pdb_ids التجريبية المرتبطة به.
يُستخدم هذا في أكثر من مكان (protein_search.py و sequence_matcher.py)
لذلك تم فصله هنا لتفادي تكرار نفس منطق استعلام RCSB.
"""

import requests

RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"


def get_pdb_ids_for_uniprot(uniprot_id: str) -> list[str]:
    """
    يرجع قائمة بمعرفات PDB التجريبية (إن وجدت) المرتبطة بمعرف UniProt معين.
    يرجع قائمة فارغة عند عدم وجود نتائج أو فشل الاتصال.
    """
    try:
        response = requests.post(
            RCSB_SEARCH_URL,
            json={
                "query": {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": (
                            "rcsb_polymer_entity_container_identifiers."
                            "reference_sequence_identifiers.database_accession"
                        ),
                        "operator": "exact_match",
                        "value": uniprot_id,
                    },
                },
                "return_type": "entry",
            },
            timeout=20,
        )
        if response.status_code == 200:
            hits = response.json().get("result_set", [])
            return [hit["identifier"] for hit in hits]
    except requests.RequestException:
        pass
    return []
