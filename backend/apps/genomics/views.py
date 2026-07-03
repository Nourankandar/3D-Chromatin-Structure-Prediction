"""
apps/genomics/views.py
REST endpoints for genomics: CellType / InputData / OutputData CRUD,
plus the pipeline-trigger endpoints (run-test, test-status, visualization-data)
and a lightweight UniProt protein search used by the frontend.
"""

import logging
import os

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CellType, InputData, OutputData
from .serializers import (
    CellTypeSerializer,
    InputDataCreateSerializer,
    InputDataSerializer,
    OutputDataSerializer,
)
from .tasks import run_genomic_pipeline_task

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Full CRUD ViewSets — one per model
# ─────────────────────────────────────────────────────────────────────────────
class CellTypeViewSet(viewsets.ModelViewSet):
    """
    GET    /api/genomics/cell-types/        -> list cell types (wrapped as {"cell_types": [...]})
    POST   /api/genomics/cell-types/        -> create a cell type
    GET    /api/genomics/cell-types/<id>/   -> retrieve a cell type
    PUT    /api/genomics/cell-types/<id>/   -> replace a cell type
    PATCH  /api/genomics/cell-types/<id>/   -> partially update a cell type
    DELETE /api/genomics/cell-types/<id>/   -> delete a cell type
    """

    queryset = CellType.objects.all().order_by('name')
    serializer_class = CellTypeSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name']

    def list(self, request, *args, **kwargs):
        # The frontend (dashboard_v3.js) expects {"cell_types": [...]}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"cell_types": serializer.data})


class InputDataViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for genomic test submissions (InputData).

    GET    /api/genomics/inputs/        -> list all genomic tests
    POST   /api/genomics/inputs/        -> create a test record directly (no pipeline trigger)
    GET    /api/genomics/inputs/<id>/   -> retrieve a test
    PUT    /api/genomics/inputs/<id>/   -> replace a test
    PATCH  /api/genomics/inputs/<id>/   -> partially update a test
    DELETE /api/genomics/inputs/<id>/   -> delete a test

    NOTE: to actually run the prediction pipeline (upload a FASTA file and
    queue the Celery task), use POST /api/genomics/run-test/ instead — this
    plain CRUD endpoint is for direct data management / testing.
    """

    queryset = InputData.objects.select_related('patient', 'cell_type').all()
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    search_fields = ['chromosome', 'status']
    ordering_fields = ['created_at', 'status']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return InputDataCreateSerializer
        return InputDataSerializer


class OutputDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Outputs are produced exclusively by the pipeline, so this endpoint is
    read-only — use it to inspect generated files for a given test.

    GET /api/genomics/outputs/        -> list all pipeline outputs
    GET /api/genomics/outputs/<id>/   -> retrieve a single output
    """

    queryset = OutputData.objects.select_related('input_data__patient', 'input_data__cell_type').all()
    serializer_class = OutputDataSerializer
    permission_classes = [IsAuthenticated]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/genomics/run-test/
# ─────────────────────────────────────────────────────────────────────────────
class RunGenomicTestAPIView(APIView):
    """
    Accepts:
        - fasta_file   : FASTA file (multipart) for the patient
        - patient_id   : int
        - cell_type_id : int
        - chromosome   : str, e.g. "chr21"
        - start_pos    : int
        - end_pos      : int

    Returns 202 Accepted + input_data_id immediately, then runs the pipeline
    asynchronously via Celery.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        fasta_file = request.FILES.get("fasta_file") or request.FILES.get("dna_sequence_file")
        if not fasta_file:
            return Response(
                {"error": "fasta_file is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        patient_id = request.data.get("patient_id") or request.data.get("patient")
        cell_type_id = request.data.get("cell_type_id") or request.data.get("cell_type")
        chromosome = request.data.get("chromosome")
        start_pos = request.data.get("start_pos")
        end_pos = request.data.get("end_pos")

        if not all([patient_id, cell_type_id, chromosome, start_pos, end_pos]):
            return Response(
                {"error": "patient_id, cell_type_id, chromosome, start_pos, and end_pos are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fasta_dir = os.path.join(settings.MEDIA_ROOT, "genomics", "sequences", str(patient_id))
        os.makedirs(fasta_dir, exist_ok=True)
        fasta_path = os.path.join(fasta_dir, fasta_file.name)

        with open(fasta_path, "wb") as f:
            for chunk in fasta_file.chunks():
                f.write(chunk)

        relative_fasta_path = os.path.relpath(fasta_path, settings.MEDIA_ROOT)

        input_data = InputData.objects.create(
            patient_id=patient_id,
            cell_type_id=cell_type_id,
            chromosome=chromosome,
            start_pos=start_pos,
            end_pos=end_pos,
            dna_sequence_file=relative_fasta_path,
            status="pending",
        )

        run_genomic_pipeline_task.delay(input_data.id)

        return Response(
            {
                "message": "Genomic test queued successfully",
                "input_data_id": input_data.id,
                "status": "pending",
            },
            status=status.HTTP_202_ACCEPTED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/genomics/test-status/<input_id>/
# ─────────────────────────────────────────────────────────────────────────────
class TestStatusAPIView(APIView):
    """
    Returns the current status of a test, for live dashboard polling.
    Statuses: pending | predicting_dnase | generating_hic |
              generating_hic_coords | scanning_motifs | completed | failed
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, input_id):
        try:
            input_data = InputData.objects.select_related("patient", "cell_type").get(pk=input_id)
        except InputData.DoesNotExist:
            return Response({"error": "InputData not found"}, status=status.HTTP_404_NOT_FOUND)

        response = {
            "input_data_id": input_data.id,
            "status": input_data.status,
            "patient": input_data.patient.name,
            "chromosome": input_data.chromosome,
            "cell_type": input_data.cell_type.name,
            "created_at": input_data.created_at,
        }

        if input_data.status == "completed":
            try:
                output = OutputData.objects.get(input_data=input_data)
                response["output_data_id"] = output.id
            except OutputData.DoesNotExist:
                pass

        return Response(response, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/genomics/visualization-data/<output_id>/
# ─────────────────────────────────────────────────────────────────────────────
class GetVisualizationDataAPIView(APIView):
    """
    The frontend's main data feed — assembles absolute URLs for the patient
    vs. reference (split-view) files, plus the scanned-protein dictionary.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, output_id):
        try:
            output = OutputData.objects.select_related(
                "input_data__patient",
                "input_data__cell_type",
                "input_data",
            ).get(pk=output_id)
        except OutputData.DoesNotExist:
            return Response({"error": "OutputData not found"}, status=status.HTTP_404_NOT_FOUND)

        input_data = output.input_data

        def to_absolute_url(file_field):
            if not file_field or not file_field.name:
                return None
            return request.build_absolute_uri(file_field.url)

        base_media_url = request.build_absolute_uri(settings.MEDIA_URL)
        proteins_payload = []
        for protein_id, info in (output.affected_proteins or {}).items():
            pdb_rel_path = info.get("pdb_file", "")
            pdb_url = f"{base_media_url}{pdb_rel_path}" if pdb_rel_path else None

            proteins_payload.append(
                {
                    "protein_id": protein_id,
                    "pdb_url": pdb_url,
                    "position": info.get("position"),
                    "rotation": info.get("rotation"),
                    "binding_score": info.get("binding_score"),
                    "is_missing": info.get("is_missing", False),
                }
            )

        response_data = {
            "meta": {
                "output_data_id": output.id,
                "patient_name": input_data.patient.name,
                "chromosome": input_data.chromosome,
                "cell_type": input_data.cell_type.name,
                "generated_at": output.generated_at,
            },
            "hic": {
                "patient_matrix_url": to_absolute_url(output.hic_patient_file),
                "reference_matrix_url": to_absolute_url(output.hic_control_file),
            },
            "dnase": {
                "patient_dnase_url": to_absolute_url(input_data.predicted_dnase_patient),
                "reference_dnase_url": to_absolute_url(input_data.predicted_dnase_control),
            },
            "coordinates_3d": {
                "patient_xyz_json_url": to_absolute_url(output.coords_patient_file),
                "reference_xyz_json_url": to_absolute_url(output.coords_control_file),
                "format": "json",
            },
            "proteins": proteins_payload,
        }

        return Response(response_data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/genomics/search-protein/?gene=<gene_name>
# ─────────────────────────────────────────────────────────────────────────────
class SearchProteinAPIView(APIView):
    """
    Looks up a gene symbol in UniProt and returns the matching protein name,
    UniProt accession, and any PDB structure IDs found in RCSB — used by the
    frontend's "search protein by gene" widget to populate the 3D viewer.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        gene = request.query_params.get("gene", "").strip()
        if not gene:
            return Response({"error": "Query parameter 'gene' is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from services.scanning_motifs.protein_search import search_protein_by_gene

            result = search_protein_by_gene(gene)
        except Exception as exc:
            logger.exception("[SearchProtein] lookup failed for gene=%s", gene)
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        if not result:
            return Response({"error": f"No UniProt entry found for gene '{gene}'"}, status=status.HTTP_404_NOT_FOUND)

        return Response(result, status=status.HTTP_200_OK)
