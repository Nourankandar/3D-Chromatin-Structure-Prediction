"""
apps/proteomics/serializers.py
"""

from rest_framework import serializers
from .models import ProteinInputData, ProteinOutputData


class ProteinOutputDataSerializer(serializers.ModelSerializer):
    """
    يُستخدم عند دمجه داخل تفاصيل الـ input (endpoint /api/proteomics/<id>/)
    وأيضاً بمساره الخاص الكامل /api/proteomics/output/<output_id>/full/
    """

    class Meta:
        model = ProteinOutputData
        fields = [
            "id",
            "patient_aa_sequence",
            "control_aa_sequence",
            "matched_protein_name",
            "matched_uniprot_id",
            "matched_pdb_id",
            "match_identity_percent",
            "structure_source",
            "structure_file",
            "confidence_score",
            "amino_acid_comparison",
            "mutation_summary",
            "generated_at",
        ]
        read_only_fields = fields  # هذا الموديل يُبنى فقط من الـ pipeline، لا يُعدّل يدوياً


class ProteinInputDataListSerializer(serializers.ModelSerializer):
    """
    نسخة مختصرة تُستخدم بقائمة التحليلات (GET /api/proteomics/)
    - بدون تفاصيل الـ output الكاملة، فقط الحالة والمعلومات الأساسية.
    """

    class Meta:
        model = ProteinInputData
        fields = [
            "id",
            "test_label",
            "chromosome",
            "start_pos",
            "end_pos",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]


class ProteinInputDataDetailSerializer(serializers.ModelSerializer):
    """
    نسخة كاملة تدمج الـ input مع الـ output (إن وُجد)
    - تُستخدم في GET /api/proteomics/<id>/
    """

    output_data = ProteinOutputDataSerializer(read_only=True)

    class Meta:
        model = ProteinInputData
        fields = [
            "id",
            "patient",
            "test_label",
            "dna_sequence_file",
            "dna_control_file",
            "chromosome",
            "start_pos",
            "end_pos",
            "status",
            "created_at",
            "output_data",
        ]
        read_only_fields = ["id", "status", "created_at", "output_data"]


class ProteinInputDataCreateSerializer(serializers.ModelSerializer):
    """
    يُستخدم فقط عند إنشاء تحليل جديد (POST /api/proteomics/run-test/)
    """

    class Meta:
        model = ProteinInputData
        fields = [
            "patient",
            "test_label",
            "dna_sequence_file",
            "chromosome",
            "start_pos",
            "end_pos",
        ]
        # dna_control_file غير موجود هنا عمداً - بيتولد تلقائياً بالـ pipeline
        # (كما هو موضح بتعليق الحقل بالموديل: "يتولد تلقائياً")


class TestStatusSerializer(serializers.ModelSerializer):
    """نسخة خفيفة جداً - تُستخدم فقط لـ polling الحالة (GET /test-status/<id>/)"""

    class Meta:
        model = ProteinInputData
        fields = ["id", "status"]
        read_only_fields = fields