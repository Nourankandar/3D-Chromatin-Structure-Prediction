# ProteinStructures/protein_fetcher.py
import requests
import os

class ProteinStructureFetcher:
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = os.path.dirname(__file__)
        self.rcsb_dir = os.path.join(cache_dir, "rcsb")
        self.alphafold_dir = os.path.join(cache_dir, "alphafold")
        os.makedirs(self.rcsb_dir, exist_ok=True)
        os.makedirs(self.alphafold_dir, exist_ok=True)

    def fetch(self, protein_name: str) -> str:
        protein_name_upper = protein_name.upper()
        
        # 1. تحويل اسم الجين إلى معرف UniProt ID
        print(f"[+] جاري البحث في UniProt عن الجين: {protein_name_upper}")
        queries = [
            f"gene:{protein_name_upper} AND organism_id:9606 AND reviewed:true",
            f"gene:{protein_name_upper} AND organism_id:9606"
        ]
        
        uniprot_id = None
        for query in queries:
            try:
                r = requests.get(
                    "https://rest.uniprot.org/uniprotkb/search",
                    params={"query": query, "fields": "accession", "format": "json", "size": 1},
                    timeout=20
                )
                if r.status_code == 200:
                    results = r.json().get("results", [])
                    if results:
                        uniprot_id = results[0]["primaryAccession"]
                        print(f"[+] تم العثور على المعرف في UniProt: {uniprot_id}")
                        break
            except Exception:
                continue

        if not uniprot_id:
            raise ValueError(f"لم يتم العثور على UniProt ID للبروتين: {protein_name}")

        # 2. البحث في قاعدة البيانات التجريبية RCSB PDB
        print(f"[+] جاري البحث في RCSB PDB عن هيكل للمعرف: {uniprot_id}")
        pdb_id = None
        try:
            r = requests.post(
                "https://search.rcsb.org/rcsbsearch/v2/query",
                json={
                    "query": {
                        "type": "terminal",
                        "service": "text",
                        "parameters": {
                            "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                            "operator": "exact_match",
                            "value": uniprot_id
                        }
                    },
                    "return_type": "entry"
                },
                timeout=20
            )
            if r.status_code == 200:
                result_data = r.json()
                if result_data and "result_set" in result_data and len(result_data["result_set"]) > 0:
                    pdb_id = result_data["result_set"][0]["identifier"]
                    print(f"[+] تم العثور على معرّف الهيكل التجريبي (PDB ID): {pdb_id}")
        except Exception as e:
            print(f"[!] لم نجد هيكل متبلور تجريبي، سننتقل للخيار البديل. السبب الفني: {e}")

        if pdb_id:
            cache_path = os.path.join(self.rcsb_dir, f"{pdb_id}.pdb")        # ← rcsb_dir
            if not os.path.exists(cache_path):
                print(f"[+] جاري تنزيل ملف PDB المشتق مخبرياً لـ {pdb_id}...")
                r = requests.get(f"https://files.rcsb.org/download/{pdb_id}.pdb", timeout=30)
                r.raise_for_status()
                with open(cache_path, "w") as f:
                    f.write(r.text)
            return cache_path
        else:
            print(f"[⚠️] جاري جلب هيكل تنبؤي من AlphaFold DB للمعرف: {uniprot_id}")
            alphafold_path = os.path.join(self.alphafold_dir, f"AF-{uniprot_id}-F1.pdb")
            
            if not os.path.exists(alphafold_path):
                api_url = f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
                try:
                    api_response = requests.get(api_url, timeout=20)
                    if api_response.status_code == 200 and api_response.json():
                        af_url = api_response.json()[0]["pdbUrl"]
                        print(f"[+] رابط التحميل المستقر من AlphaFold: {af_url}")
                        
                        r = requests.get(af_url, timeout=30)
                        r.raise_for_status()
                        with open(alphafold_path, "w") as f:
                            f.write(r.text)
                        print(f"[+] تم حفظ مصفوفة الذرات الفراغية بنجاح.")
                    else:
                        raise ValueError("لم يرجع سيرفر AlphaFold بيانات لهذا المعرف.")
                except Exception as e:
                    raise ValueError(f"فشل جلب الملف للبروتين {protein_name_upper} من المصدرين: {e}")
            
            return alphafold_path