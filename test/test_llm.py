import os
from ai_engine.models.LLM_Report.report_generator import generate_clinical_llm_report

print("⏳ جاري بدء فحص الاتصال بـ Gemini API لتوليد التقرير...")

# بيانات تجريبية تحاكي المخرجات الحقيقية للـ Pipeline
patient_data = {
    "cell_type": "Liver Cell (HepG2)",
    "chromosome": "Chromosome 21"
}

alignment_info = {
    "coordinates": "chr21:34,800,000-35,200,000",
    "mutation_details": "Single Nucleotide Polymorphism (SNP) at CTCF binding hotspot",
    "disrupted_motifs": "MA0139.1 (CTCF Motif)"
}

delta_analysis = {
    "matrix_difference_summary": "Significant drop in chromatin contact frequency inside TAD boundary.",
    "loop_status": "Collapsed chromatin loop affecting structural promoter-enhancer communication.",
    "affected_genes": "RUNX1, ERG"
}

missing_proteins = ["CTCF", "RAD21 (Cohesin Complex)"]

# استدعاء الدالة
report = generate_clinical_llm_report(patient_data, alignment_info, delta_analysis, missing_proteins)

print("\n================== التقرير الطبي الناتجة ==================\n")
print(report)
print("\n===========================================================\n")


