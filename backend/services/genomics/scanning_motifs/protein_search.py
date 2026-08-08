"""
services/scanning_motifs/protein_search.py
Lightweight UniProt + RCSB PDB lookup used by the "search protein by gene"
endpoint. Unlike ProteinStructureFetcher (which downloads and caches the
full .pdb structure as part of the prediction pipeline), this only resolves
identifiers for quick frontend lookups — no large files are downloaded.
"""

import requests

UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_protein_names_for_genes_batch(
    gene_names: list[str],
    organism_id: int = 9606,
    max_results: int = 5,
    max_workers: int = 8,
) -> dict[str, list[str]]:
    """
    نفس منطق get_protein_names_for_gene بس بيشغّل كل الطلبات بالتوازي
    (threads — الشغلة I/O-bound أصلاً، مش CPU-bound، فـ threading هون فعّال
    رغم الـ GIL). بيرجع dict: {gene_name: [protein_names]}.

    لو جين معين فشل، بيرجع له [] بس — باقي الجينات ما بتتأثر.
    """
    results: dict[str, list[str]] = {}

    if not gene_names:
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_gene = {
            executor.submit(get_protein_names_for_gene, gene, organism_id, max_results): gene
            for gene in gene_names
        }
        for future in as_completed(future_to_gene):
            gene = future_to_gene[future]
            try:
                results[gene] = future.result()
            except Exception:
                # get_protein_names_for_gene أصلاً ما بترمي، بس منحمي حالنا زيادة
                results[gene] = []

    return results
def get_protein_names_for_gene(gene: str, organism_id: int = 9606, max_results: int = 5) -> list[str]:
    """
    يرجع ليستة أسماء البروتينات المرتبطة بجين معيّن (UniProt فقط — بدون PDB،
    مصممة لتكون خفيفة وآمنة للاستخدام جوا لوب على كل جينات الـ pipeline).

    - بترجع لستة فاضية [] بأي حالة فشل (شبكة، timeout، ما في نتائج...) —
      ما بترمي Exception أبداً، حتى ما توقف تشغيل الـ pipeline كامل بسبب
      جين واحد أو مشكلة اتصال مؤقتة.
    - بتاخد أول reviewed entry إذا موجود (أدق)، وإلا بترجع من أي entry.
    - بتشيل التكرار (لو نفس اسم البروتين طلع أكتر من مرة).
    """
    gene_upper = gene.upper()
    queries = [
        f"gene:{gene_upper} AND organism_id:{organism_id} AND reviewed:true",
        f"gene:{gene_upper} AND organism_id:{organism_id}",
    ]

    for query in queries:
        try:
            response = requests.get(
                UNIPROT_SEARCH_URL,
                params={
                    "query": query,
                    "fields": "protein_name",
                    "format": "json",
                    "size": max_results,
                },
                timeout=10,
            )
        except requests.RequestException:
            continue

        if response.status_code != 200:
            continue

        results = response.json().get("results", [])
        if not results:
            continue

        protein_names = []
        for entry in results:
            try:
                name = entry["proteinDescription"]["recommendedName"]["fullName"]["value"]
            except (KeyError, TypeError):
                continue
            if name and name not in protein_names:
                protein_names.append(name)

        if protein_names:
            return protein_names

    return []
def search_protein_by_gene(gene: str, organism_id: int = 9606) -> dict | None:
    """
    Resolve a gene symbol (e.g. "CTCF") to a UniProt accession, protein name,
    and any associated experimentally-determined PDB structure IDs.

    Returns a dict shaped like:
        {
            "gene": "CTCF",
            "uniprot_id": "P49711",
            "protein_name": "Transcriptional repressor CTCF",
            "pdb_ids": ["8SSS", "8SST"],
        }
    or None if no UniProt entry could be found.
    """
    gene_upper = gene.upper()
    queries = [
        f"gene:{gene_upper} AND organism_id:{organism_id} AND reviewed:true",
        f"gene:{gene_upper} AND organism_id:{organism_id}",
    ]

    uniprot_id = None
    protein_name = gene_upper
    for query in queries:
        response = requests.get(
            UNIPROT_SEARCH_URL,
            params={
                "query": query,
                "fields": "accession,protein_name",
                "format": "json",
                "size": 1,
            },
            timeout=20,
        )
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                entry = results[0]
                uniprot_id = entry["primaryAccession"]
                try:
                    protein_name = entry["proteinDescription"]["recommendedName"]["fullName"]["value"]
                except (KeyError, TypeError):
                    pass
                break

    if not uniprot_id:
        return None

    pdb_ids = []
    try:
        pdb_response = requests.post(
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
        if pdb_response.status_code == 200:
            hits = pdb_response.json().get("result_set", [])
            pdb_ids = [hit["identifier"] for hit in hits]
    except requests.RequestException:
        pdb_ids = []

    return {
        "gene": gene_upper,
        "uniprot_id": uniprot_id,
        "protein_name": protein_name,
        "pdb_ids": pdb_ids,
    }
