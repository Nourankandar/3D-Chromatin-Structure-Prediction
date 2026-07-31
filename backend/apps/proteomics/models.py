import os
from django.db import models


def protein_file_upload_path(instance, filename):
    """
    مسار حفظ ملفات الـ FASTA والـ PDB الخاصة بتحليلات البروتين
    """
    return os.path.join("proteomics", f"patient_{instance.patient.id}", filename)


class ProteinInputData(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        TRANSLATING = "translating", "Translating DNA"
        MATCHING = "matching", "Matching Protein"
        PREDICTING_STRUCTURE = "predicting_structure", "Predicting 3D Structure"
        CANCELLING = "cancelling", "Cancelling"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="protein_tests",
        verbose_name="Patient",
    )
    test_label = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="اسم اختياري يدخله المستخدم للتمييز بين الفحوصات",
    )
    dna_sequence_file = models.FileField(
        upload_to=protein_file_upload_path,
        help_text="ملف FASTA لتسلسل المريض",
    )
    dna_control_file = models.FileField(
        upload_to=protein_file_upload_path,
        blank=True,
        null=True,
        help_text="التسلسل السليم المقابل (يتولد تلقائياً)",
    )
    chromosome = models.CharField(max_length=50, blank=True, null=True)
    start_pos = models.BigIntegerField(blank=True, null=True)
    end_pos = models.BigIntegerField(blank=True, null=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Protein Input Data"
        verbose_name_plural = "Protein Input Data Records"

    def save(self, *args, **kwargs):
        # توليد اسم تلقائي للتحليل في حال لم يدخله المستخدم
        if not self.test_label and not self.pk:
            super().save(*args, **kwargs)
            date_str = self.created_at.strftime("%Y-%m-%d") if self.created_at else ""
            self.test_label = f"Protein Test #{self.pk} - {date_str}".strip(" -")
            return super().save(update_fields=["test_label"])
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.test_label} (Patient ID: {self.patient_id})"


class ProteinOutputData(models.Model):
    class StructureSource(models.TextChoices):
        PDB_EXPERIMENTAL = "pdb_experimental", "Experimental (PDB/RCSB)"
        ESMFOLD_PREDICTED = "esmfold_predicted", "Predicted (ESMFold)"

    input_data = models.OneToOneField(
        ProteinInputData,
        on_delete=models.CASCADE,
        related_name="output_data",
        verbose_name="Input Data Reference",
    )
    patient_aa_sequence = models.TextField(
        help_text="سلسلة الأحماض الأمينية للمريض"
    )
    control_aa_sequence = models.TextField(
        help_text="سلسلة الأحماض الأمينية السليمة"
    )
    
    # تفاصيل المطابقة
    matched_protein_name = models.CharField(max_length=255, blank=True, null=True)
    matched_uniprot_id = models.CharField(max_length=100, blank=True, null=True)
    matched_pdb_id = models.CharField(max_length=100, blank=True, null=True)
    match_identity_percent = models.FloatField(blank=True, null=True)

    # تفاصيل البنية
    structure_source = models.CharField(
        max_length=30,
        choices=StructureSource.choices,
        help_text="المفتاح الذي يحدد نوع الثقة بالنتيجة للفرونت إند",
    )
    structure_file = models.FileField(
        upload_to=protein_file_upload_path,
        help_text="ملف البنية 3D بصيغة PDB",
    )
    confidence_score = models.FloatField(
        blank=True,
        null=True,
        help_text="درجة الثقة pLDDT (فارغ في حال البنية معملية)",
    )

    # المقارنات والإحصائيات
    amino_acid_comparison = models.JSONField(
        default=dict,
        help_text="جدول المقارنة الكامل (موقع، حمض سليم، حمض مريض، نوع الطفرة)",
    )
    mutation_summary = models.JSONField(
        default=dict,
        help_text="إحصائيات عدد الطفرات وتصنيفها",
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]
        verbose_name = "Protein Output Data"
        verbose_name_plural = "Protein Output Data Records"

    def __str__(self):
        return f"Output for {self.input_data.test_label}"