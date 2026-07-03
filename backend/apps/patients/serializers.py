"""
apps/patients/serializers.py
"""

from rest_framework import serializers

from .models import Patient


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class PatientListSerializer(serializers.ModelSerializer):
    """Lighter-weight representation used for list views / dropdowns."""

    class Meta:
        model = Patient
        fields = ['id', 'mrn', 'name', 'gender', 'dob']
