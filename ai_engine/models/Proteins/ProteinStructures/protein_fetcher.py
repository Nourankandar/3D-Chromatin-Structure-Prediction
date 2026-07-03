# ProteinStructures/protein_fetcher.py
import requests
import os

class ProteinStructureFetcher:
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), "pdb_cache")
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def fetch(self, protein_name: str) -> str:
        """
        Input:  protein_name  مثل "CTCF" أو "Spz1"
        Output: مسار ملف .pdb (من RCSB PDB أو AlphaFold كخيار احتياطي)
        """
        protein_name_upper = protein_name.upper()
        
        # ١. اسم البروتين → UniProt ID
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
            raise ValueError(f"ما لقيت UniProt ID للبروتين: {protein_name}")

        # ٢. محاولة جلب الهيكل من RCSB PDB
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
                hits = r.json().get("result_set", [])
                if hits:
                    pdb_id = hits[0]["identifier"]
                    print(f"[+] تم العثور على معرّف الهيكل التجريبي (PDB ID): {pdb_id}")
        except Exception:
            print("[!] لم يتم العثور على هيكل تجريبي في RCSB PDB أو السيرفر لم يستجب.")

        # ٣. تنزيل الملف بناءً على المصدر المتاح
        if pdb_id:
            # تنزيل من RCSB PDB
            cache_path = os.path.join(self.cache_dir, f"{pdb_id}.pdb")
            if not os.path.exists(cache_path):
                print(f"[+] جاري تنزيل ملف PDB الخاص بـ {pdb_id} من RCSB PDB...")
                r = requests.get(f"https://files.rcsb.org/download/{pdb_id}.pdb", timeout=30)
                r.raise_for_status()
                with open(cache_path, "w") as f:
                    f.write(r.text)
            return cache_path
        else:
            # خيار احتياطي متطور: التنزيل من AlphaFold API المستقر
            print(f"[⚠️] لا يوجد هيكل متبلور لـ {protein_name_upper} في PDB. جاري التوجه لـ AlphaFold DB...")
            alphafold_path = os.path.join(self.cache_dir, f"AF-{uniprot_id}-F1.pdb")
            
            if not os.path.exists(alphafold_path):
                # استعلام الـ API لمعرفة رابط الـ pdb الصحيح لـ Q9BXG8 حالياً
                api_url = f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
                try:
                    api_response = requests.get(api_url, timeout=20)
                    if api_response.status_code == 200 and api_response.json():
                        # استخراج رابط ملف pdb الديناميكي من الـ API
                        af_url = api_response.json()[0]["pdbUrl"]
                        print(f"[+] تم جلب رابط التحميل الحديث من AlphaFold: {af_url}")
                        
                        # تحميل الملف الفعلي
                        r = requests.get(af_url, timeout=30)
                        r.raise_for_status()
                        with open(alphafold_path, "w") as f:
                            f.write(r.text)
                        print(f"[+] تم تحميل هيكل AlphaFold بنجاح حفظه في الكاش!")
                    else:
                        raise ValueError("الـ API الخاص بـ AlphaFold لم يرجع أي بيانات للبروتين.")
                except Exception as e:
                    raise ValueError(f"فشل جلب هيكل للبروتين {protein_name_upper} من PDB ومن AlphaFold أيضاً. التفاصيل: {e}")
            
            return alphafold_path