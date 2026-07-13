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
from rest_framework.decorators import action
from .models import CellType, InputData, OutputData
from .serializers import (
    CellTypeSerializer,
    InputDataCreateSerializer,
    InputDataSerializer,
    OutputDataSerializer,
)
from .tasks import run_genomic_pipeline_task
from rest_framework.filters import SearchFilter
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
    filter_backends = [SearchFilter]

    def list(self, request, *args, **kwargs):
        # The frontend (dashboard_v3.js) expects {"cell_types": [...]}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"cell_types": serializer.data})


class InputDataViewSet(viewsets.ModelViewSet):
    queryset = InputData.objects.select_related('patient', 'cell_type').prefetch_related('output').all()
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    search_fields = ['chromosome', 'status']
    ordering_fields = ['created_at', 'status']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return InputDataCreateSerializer
        return InputDataSerializer

    def list(self, request, *args, **kwargs):
        # الشرط: patient_id إلزامي
        patient_id = request.query_params.get('patient_id')
        if not patient_id:
            return Response(
                {"error": "The 'patient_id' query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        queryset = self.filter_queryset(self.get_queryset()).filter(patient_id=patient_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # بنأخذ البيانات الأساسية للـ Input
        data = serializer.data
        
        # بنجيب الـ output المرتبط فيه لو موجود (بفضل الـ OneToOneField)
        output_obj = getattr(instance, 'output', None)
        if output_obj:
            # استخدمنا السيريالايزر تبعك مباشرة
            data['output'] = OutputDataSerializer(output_obj).data
        else:
            # لو كان لسا pending أو عم يعالج وما نزل له مخرجات
            data['output'] = None
            
        return Response(data)

    @action(detail=True, methods=["post"], url_path="stop")
    def stop(self, request, pk=None):
        input_data = self.get_object()

        if input_data.status in ("completed", "failed", "cancelled"):
            return Response(
                {"error": f"Cannot stop — analysis already '{input_data.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # نكتفي بوضع علم "طلب إلغاء" — الـ pipeline_manager رح يفحصه بين كل خطوة ويوقف الشغل فوراُ
        input_data.status = "cancelling"
        input_data.save(update_fields=["status"])

        return Response(
            {"message": "Cancellation requested", "input_data_id": input_data.id, "status": "cancelling"},
            status=status.HTTP_202_ACCEPTED,
        )

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
        # 1) التحقق فوراً: هل هناك أي تحليل شغال حالياً في الخلفية؟
        active_statuses = [
            'pending', 
            'predicting_dnase', 
            'generating_hic', 
            'generating_hic_coords', 
            'scanning_motifs', 
            'cancelling'
        ]
        
        has_active_test = InputData.objects.filter(status__in=active_statuses).exists()
        
        if has_active_test:
            return Response(
                {"error": "There is already a genomic test running. Please wait until it finishes or stop it before running a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2) إذا لم يكن هناك أي تحليل شغال، يكمل الكود الطبيعي تبعك:
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
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, input_id):
        try:
            # جلب البيانات مع العلاقات بضربة واحدة سريعة
            input_data = InputData.objects.select_related("patient", "cell_type").prefetch_related("output").get(pk=input_id)
        except InputData.DoesNotExist:
            return Response({"error": "InputData not found"}, status=status.HTTP_404_NOT_FOUND)

        response = {
            "input_data_id": input_data.id,
            "status": input_data.status,
            "patient": input_data.patient.name,
            "chromosome": input_data.chromosome,
            "cell_type": input_data.cell_type.name,
            "created_at": input_data.created_at,
            "output_data_id": None  # قيمة افتراضية
        }

        # التحقق من وجود output مباشرة دون استعلام إضافي بفضل الـ prefetch
        output_obj = getattr(input_data, 'output', None)
        if input_data.status == "completed" and output_obj:
            response["output_data_id"] = output_obj.id

        return Response(response, status=status.HTTP_200_OK)

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
