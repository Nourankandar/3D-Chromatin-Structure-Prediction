from django.db import models

from apps.genomics.models import OutputData


class AnalysisReport(models.Model):
    """The AI-generated clinical report tied to one pipeline OutputData."""

    REPORT_STATUS = [
        ('draft', 'Draft (Pending Review)'),
        ('generating', 'Generating'),
        ('published', 'Published'),
        ('approved', 'Approved'),
        ('failed', 'Failed'),
    ]

    output_data = models.OneToOneField(OutputData, on_delete=models.CASCADE, related_name='report')
    detected_disease = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Detected Condition / Disease"
    )
    summary_text = models.TextField(
        verbose_name="Medical Summary & Structural Analysis", blank=True, null=True
    )
    status = models.CharField(max_length=12, choices=REPORT_STATUS, default='draft', verbose_name="Report Status")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Medical Report for Output ID: {self.output_data.id} - Status: {self.status}"

    class Meta:
        verbose_name = "Analysis Report"
        verbose_name_plural = "Analysis Reports"
        ordering = ['-created_at']
