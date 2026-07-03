"""
apps/reports/serializers.py
"""

from rest_framework import serializers

from .models import AnalysisReport


class AnalysisReportSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='output_data.input_data.patient.name', read_only=True)
    chromosome = serializers.CharField(source='output_data.input_data.chromosome', read_only=True)

    class Meta:
        model = AnalysisReport
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
