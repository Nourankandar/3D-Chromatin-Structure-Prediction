import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

def generate_clinical_llm_report(patient_data, alignment_info, delta_analysis, missing_proteins):
    """
    توليد التقرير الطبي جينومياً باستخدام مكتبة Google GenAI الرسمية والحديثة
    متوافق مع الاستدعاء الخارجي والداخلي وقراءة ملف الـ .env المركزي.
    """
    # 1. البحث عن ملف .env في جذر المشروع الحالي الذي يتم تشغيل الأمر منه
    env_path = Path('.env').resolve()
    if not env_path.exists():
        # محاولة البحث كـ Fallback في جذر المشروع بناءً على الهيكلية المعتادة
        env_path = Path(__file__).resolve().parents[3] / '.env'
    
    # تحميل المتغيرات
    load_dotenv(dotenv_path=env_path)

    # 2. تنظيف بيئة السكربت فوراً لمنع المكتبة من قراءة أي توكن عام تالف مخزن بالويندوز
    if "GOOGLE_API_KEY" in os.environ:
        del os.environ["GOOGLE_API_KEY"]
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

    # 3. التحقق من أن المفتاح تم التقاطه بنجاح
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"[LLM_Report] خطأ: لم يتم العثور على GEMINI_API_KEY. تم البحث في المسار: {env_path}")
        return "Error: Missing GEMINI_API_KEY in .env file."

    try:
        # 4. تمرير المفتاح مباشرة عند بناء الكلاينت لمنع تضارب التوكنز بالخلفية
        client = genai.Client(api_key=api_key)

        # 5. تجهيز لستة البروتينات المتأثرة بشكل نصي
        proteins_list_str = ", ".join(missing_proteins) if missing_proteins else "None detected"

        # 6. صياغة التعليمات البرمجية وهندسة الـ Prompt لمشروع الـ Chromatin
        system_instruction = (
            "You are an expert clinical geneticist and computational biologist. "
            "Your role is to write a highly professional, structured biomedical report based on the provided 3D chromatin profiling data. "
            "Focus heavily on structural variations, loop disruptions, and spatial interactions of proteins."
        )

        user_context = f"""
        === RECONSTRUCTED GENOMIC CASE DATA ===
        - Cell Type Context: {patient_data.get('cell_type')}
        - Target Chromosome: {patient_data.get('chromosome')}
        - Reference Genome Mapping Coordinates (hg38): {alignment_info.get('coordinates')}
        - Structural Variation Detail: {alignment_info.get('mutation_details')}
        
        === 3D CHROMATIN ARCHITECTURE (Hi-C INTERACTION DELTA) ===
        - Matrix Divergence Summary: {delta_analysis.get('matrix_difference_summary')}
        - Chromatin Loop Alteration Status: {delta_analysis.get('loop_status')}
        - Downstream Affected Neighboring Genes: {delta_analysis.get('affected_genes')}
        
        === PROTEIN MOTIF SCANNING & DOCKING ANOMALIES ===
        - Disrupted Motif Matches (JASPAR Database): {alignment_info.get('disrupted_motifs')}
        - Lost/Displaced Structural Proteins: {proteins_list_str}
        
        === CLINICAL REPORT REQUIREMENTS ===
        Please synthesize this data into a rigorous 5-section Markdown clinical report:
        1. EXECUTIVE SUMMARY: High-level medical briefing of the genomic variance.
        2. 3D CHROMATIN IMPACT: Mechanical comparison between the healthy structure and the patient's folded chromatin.
        3. PROTEIN DOCKING DISRUPTION: Heavy clinical focus on why proteins like {proteins_list_str} failed to properly associate with the target coordinates.
        4. PATHOGENIC INTERPRETATION: How this architectural failure leads to gene expression alteration ({delta_analysis.get('affected_genes')}).
        5. RECOMMENDATIONS: Clinical follow-up paths.
        """

        # 7. استدعاء الموديل 
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_context,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            )
        )
        
        return response.text

    except Exception as e:
        print(f"[LLM_Report Error] فشل الاتصال بـ Gemini API: {e}")
        return f"Error while generating the report dynamically via Gemini: {str(e)}"