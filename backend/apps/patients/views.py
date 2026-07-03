"""
apps/patients/views.py
Full REST CRUD for Patient, plus a nested `tests` action that returns
every genomic test (InputData) belonging to a given patient.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.genomics.models import InputData
from apps.genomics.serializers import InputDataSerializer

from .models import Patient
from .serializers import PatientSerializer


class PatientViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for patients.

    GET    /api/patients/            -> list all patients
    POST   /api/patients/            -> create a patient
    GET    /api/patients/<id>/       -> retrieve a patient
    PUT    /api/patients/<id>/       -> replace a patient
    PATCH  /api/patients/<id>/       -> partially update a patient
    DELETE /api/patients/<id>/       -> delete a patient
    GET    /api/patients/<id>/tests/ -> list every genomic test for this patient
    """

    queryset = Patient.objects.all().order_by("-created_at")
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["mrn", "name"]
    ordering_fields = ["created_at", "name", "dob"]

    @action(detail=True, methods=["get"], url_path="tests")
    def get_patient_tests(self, request, pk=None):
        patient = self.get_object()

        tests = (
            InputData.objects.filter(patient=patient)
            .select_related("cell_type")
            .prefetch_related("output")
            .order_by("-created_at")
        )

        results = []
        for t in tests:
            entry = InputDataSerializer(t).data
            entry["output_data_id"] = t.output.id if hasattr(t, "output") else None
            results.append(entry)

        return Response(
            {"patient_id": patient.id, "tests": results},
            status=status.HTTP_200_OK,
        )
