from django.db import models
from apps.patients.models import Patient

class CellType(models.Model):
    """A reference cell type used to pick the Enformer prediction track."""

    name = models.CharField(max_length=50, unique=True, verbose_name="Cell Type Name")
    # target_enformer_id = models.IntegerField(verbose_name="Enformer Target Track ID")
    target_basset_track_id = models.IntegerField(verbose_name="Basset Target Track ID")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    def __str__(self):
        return self.name
    class Meta:
        verbose_name = "Cell Type"
        verbose_name_plural = "Cell Types"
        ordering = ['name']

class InputData(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('predicting_dnase', 'Predicting DNase-seq Profiles'),
        ('generating_hic', 'Generating Hi-C Matrices'),
        ('generating_hic_coords', 'Calculating 3D Coordinates'),
        ('scanning_motifs', 'Scanning Motifs & PDB Docking'),
        ('cancelling', 'Cancellation Requested'),   # جديد
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='genomic_inputs')
    cell_type = models.ForeignKey(CellType, on_delete=models.PROTECT, related_name='inputs')
    chromosome = models.CharField(max_length=10, verbose_name="Chromosome (e.g., chr21)")
    start_pos = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Start Position (bp)"
    )
    end_pos = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="End Position (bp)"
    )
    dna_sequence_file = models.FileField(
        upload_to='genomics/raw_inputs/fasta/', max_length=255, verbose_name="DNA Sequence File (Patient)"
    )
    dna_control_file = models.FileField(
        upload_to='genomics/raw_inputs/fasta/', max_length=255, verbose_name="DNA Sequence File (control) "
    )
    predicted_dnase_patient = models.FileField(
        upload_to='genomics/raw_inputs/dnas_signals/', max_length=255, null=True, blank=True,
        verbose_name="Predicted DNase File (Patient)"
    )
    predicted_dnase_control = models.FileField(
        upload_to='genomics/raw_inputs/dnas_signals/', max_length=255, null=True, blank=True,
        verbose_name="Predicted DNase File (Control)"
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending', verbose_name="Processing Status")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Last Status Update")   # ← هاد الجديد
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    def __str__(self):
        return f"Input for {self.patient.name} - {self.chromosome}:{self.start_pos}-{self.end_pos}"

    class Meta:
        verbose_name = "Genomic Input"
        verbose_name_plural = "Genomic Inputs"
        ordering = ['-created_at']


class OutputData(models.Model):
    """Pipeline outputs generated for a given InputData."""

    input_data = models.OneToOneField(InputData, on_delete=models.CASCADE, related_name='output')

    hic_patient_file = models.FileField(
        upload_to='genomics/hic_matrices/npz/', max_length=255, blank=True, null=True,
        verbose_name="Hi-C Matrix File (Patient)"
    )
    hic_control_file = models.FileField(
        upload_to='genomics/hic_matrices/npz/', max_length=255, blank=True, null=True,
        verbose_name="Hi-C Matrix File (Control)"
    )

    coords_patient_file = models.FileField(
        upload_to='genomics/coordinates_3d/json/', max_length=255, blank=True, null=True,
        verbose_name="3D Coords JSON (Patient)"
    )
    coords_control_file = models.FileField(
        upload_to='genomics/coordinates_3d/json/', max_length=255, blank=True, null=True,
        verbose_name="3D Coords JSON (Control)"
    )

    affected_proteins = models.JSONField(
        blank=True, null=True, verbose_name="Affected Proteins, PDB Paths & Docking Data"
    )

    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Genomic Output for Input ID: {self.input_data.id}"

    class Meta:
        verbose_name = "Genomic Output"
        verbose_name_plural = "Genomic Outputs"
        ordering = ['-generated_at']



class GeneProteinResult(models.Model):
    """
    نتيجة تحليل جين واحد (ترجمة + مقارنة طفرة) — سجل منفصل لكل جين
    ضمن نفس OutputData، بدل ما تكون كل الجينات مضغوطة بحقل JSON واحد
    كبير — بيسهّل الفلترة/البحث لاحقاً (مثلاً: "جيبلي كل الجينات يلي
    فيها missense" عبر ORM مباشرة بدل ما نفكك JSON بايثونياً).
    """

    MUTATION_TYPE_CHOICES = [
        ('none', 'No Mutation'),
        ('silent', 'Silent'),
        ('missense', 'Missense'),
        ('nonsense', 'Nonsense'),
        ('frameshift', 'Frameshift'),
    ]

    output_data = models.ForeignKey(
        'OutputData', on_delete=models.CASCADE, related_name='genes'
    )

    gene_id = models.CharField(max_length=50)
    gene_name = models.CharField(max_length=50, db_index=True) 
    protein_name = models.CharField(max_length=255, null=True, blank=True) 
    transcript_id = models.CharField(max_length=50)
    strand = models.CharField(max_length=1, choices=[('+', '+'), ('-', '-')])

    gene_start = models.PositiveBigIntegerField()
    gene_end = models.PositiveBigIntegerField()

    is_complete_in_patient_sample = models.BooleanField(default=True)

    error = models.TextField(null=True, blank=True)

    mutation_type = models.CharField(
        max_length=12, choices=MUTATION_TYPE_CHOICES, null=True, blank=True
    )
    mutated_codons = models.JSONField(default=list, blank=True)  

    # المريض
    patient_mrna_sequence = models.TextField(null=True, blank=True)
    patient_amino_acid_sequence = models.TextField(null=True, blank=True)
    patient_translation_warnings = models.JSONField(default=list, blank=True)

    # السليم
    control_mrna_sequence = models.TextField(null=True, blank=True)
    control_amino_acid_sequence = models.TextField(null=True, blank=True)
    control_translation_warnings = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.gene_name} ({self.mutation_type or 'error'}) — Output {self.output_data_id}"

    class Meta:
        verbose_name = "Gene Protein Analysis Result"
        verbose_name_plural = "Gene Protein Analysis Results"
        unique_together = ('output_data', 'gene_id')
        ordering = ['gene_name']