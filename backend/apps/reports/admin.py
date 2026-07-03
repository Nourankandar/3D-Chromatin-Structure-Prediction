from django.contrib import admin

from .models import AnalysisReport


@admin.register(AnalysisReport)
class AnalysisReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'output_data', 'detected_disease', 'status', 'created_at', 'updated_at']
    list_filter = ['status']
    search_fields = ['detected_disease']
