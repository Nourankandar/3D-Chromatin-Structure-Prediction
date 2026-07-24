"""
apps/genomics/serializers.py
"""

from rest_framework import serializers

from backend.core import settings

from .models import CellType, InputData, OutputData


class CellTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CellType
        fields = '__all__'
        read_only_fields = ['id']


class InputDataSerializer(serializers.ModelSerializer):
    cell_type_name = serializers.CharField(source='cell_type.name', read_only=True)
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    output_data_id = serializers.SerializerMethodField()

    class Meta:
        model = InputData
        fields = '__all__'
        read_only_fields = [
            'id', 'status', 'created_at',
            'predicted_dnase_patient', 'predicted_dnase_control',
        ]

    def get_output_data_id(self, obj):
        return obj.output.id if hasattr(obj, 'output') else None


class InputDataCreateSerializer(serializers.ModelSerializer):
    """Used for plain (non-pipeline-triggering) CRUD creation/updates of InputData."""

    class Meta:
        model = InputData
        fields = [
            'id', 'patient', 'cell_type', 'chromosome', 'start_pos', 'end_pos',
            'dna_sequence_file','dna_control_file', 'status', 'created_at',
        ]
        read_only_fields = ['id', 'status', 'created_at']


class OutputDataSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='input_data.patient.name', read_only=True)
    chromosome = serializers.CharField(source='input_data.chromosome', read_only=True)
    affected_proteins = serializers.SerializerMethodField() # تعديل مخصص هنا
    report_id = serializers.SerializerMethodField()  # ← جديد: الربط الصريح مع AnalysisReport

    class Meta:
        model = OutputData
        fields = '__all__'
        read_only_fields = ['id', 'generated_at']

    def get_report_id(self, obj):
        # OneToOneField بين OutputData و AnalysisReport — الـ id مختلف
        # عن قصد (كل جدول عندو تسلسل خاص فيه)، فلازم نرجع الربط صراحة
        # حتى الفرونت يعرف يوصل لتقرير الـ output هاد بدون أي تخمين
        return obj.report.id if hasattr(obj, 'report') else None

    def get_affected_proteins(self, obj):
        if not obj.affected_proteins:
            return []
            
        request = self.context.get('request')
        
        proteins_payload = []
        for protein_id, info in obj.affected_proteins.items():
            pdb_rel_path = info.get("pdb_file", "")

            proteins_payload.append({
                "protein_id": protein_id,
                "position": info.get("position"),
                "rotation": info.get("rotation"),
                "binding_score": info.get("binding_score"),
                "is_missing": info.get("is_missing", False),
            })
        return proteins_payload