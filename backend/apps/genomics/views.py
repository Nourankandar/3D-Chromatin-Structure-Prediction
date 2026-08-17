"""
apps/genomics/views.py
REST endpoints for genomics: CellType / InputData / OutputData CRUD,
plus the pipeline-trigger endpoints (run-test, test-status, visualization-data)
and a lightweight UniProt protein search used by the frontend.
"""

import logging
import os
from celery import current_app
from django.db import transaction
from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from .models import CellType, InputData
from backend.core.utils.atomic_utils import atomic_with_cleanup
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

        if input_data.celery_task_id:
            current_app.control.revoke(
                input_data.celery_task_id,
                terminate=True,
                signal="SIGTERM",
            )

        old_status = input_data.status

        def rollback_status():
            input_data.status = old_status
            input_data.save(update_fields=["status", "updated_at"])

        try:
            with atomic_with_cleanup(cleanup_fn=rollback_status, log_prefix="StopAnalysis"):
                input_data.status = "cancelled"
                input_data.save(update_fields=["status", "updated_at"])
        except Exception as exc:
            return Response(
                {"error": f"Failed to stop analysis: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"message": "Analysis stopped successfully", "input_data_id": input_data.id, "status": "cancelled"},
            status=status.HTTP_200_OK,
        )
# ─────────────────────────────────────────────────────────────────────────────
# POST /api/genomics/run-test/
# ─────────────────────────────────────────────────────────────────────────────
def _launch_pipeline_task(input_data_id: int) -> None:
    """
    بتنطلق بس بعد ما الـ transaction تتثبت (commit) فعلياً —
    منشان نضمن إنه InputData موجود بالداتابيز 100% قبل ما نبعت الـ task،
    وقبل ما نحاول نحفظ الـ celery_task_id عليه.
    """
    async_result = run_genomic_pipeline_task.delay(input_data_id)
    InputData.objects.filter(pk=input_data_id).update(celery_task_id=async_result.id)


class RunGenomicTestAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        active_statuses = [
            'pending', 'predicting_dnase', 'generating_hic',
            'generating_hic_coords', 'scanning_motifs', 'cancelling'
        ]

        has_active_test = InputData.objects.filter(status__in=active_statuses).exists()
        if has_active_test:
            return Response(
                {"error": "There is already a genomic test running. Please wait until it finishes or stop it before running a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        fasta_file = request.FILES.get("fasta_file") or request.FILES.get("dna_sequence_file")
        if not fasta_file:
            return Response({"error": "fasta_file is required"}, status=status.HTTP_400_BAD_REQUEST)

        patient_id = request.data.get("patient_id") or request.data.get("patient")
        cell_type_id = request.data.get("cell_type_id") or request.data.get("cell_type")
        chromosome = request.data.get("chromosome")

        if not all([patient_id, cell_type_id, chromosome]):
            return Response(
                {"error": "patient_id, cell_type_id, and chromosome are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fasta_dir = os.path.join(settings.MEDIA_ROOT, "genomics", "sequences", str(patient_id))
        os.makedirs(fasta_dir, exist_ok=True)
        fasta_path = os.path.join(fasta_dir, fasta_file.name)

        try:
            with open(fasta_path, "wb") as f:
                for chunk in fasta_file.chunks():
                    f.write(chunk)
        except OSError as exc:
            return Response(
                {"error": f"Failed to save uploaded file: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        relative_fasta_path = os.path.relpath(fasta_path, settings.MEDIA_ROOT)
        input_data = None

        def cleanup_file():
            if os.path.exists(fasta_path):
                os.remove(fasta_path)

        try:
            with atomic_with_cleanup(cleanup_fn=cleanup_file, log_prefix="RunGenomicTest"):
                input_data = InputData.objects.create(
                patient_id=patient_id,
                cell_type_id=cell_type_id,
                chromosome=chromosome,
                dna_sequence_file=relative_fasta_path,
                status="pending",
            )
                transaction.on_commit(lambda: _launch_pipeline_task(input_data.id))
        except Exception as exc:
            return Response(
                {"error": f"Failed to start genomic pipeline: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "message": "Genomic test queued successfully",
                "input_data_id": input_data.id,
                "status": "pending",
            },
            status=status.HTTP_202_ACCEPTED,
        )
    
# apps/genomics/views.py
class OutputDataFullDetailAPIView(APIView):
    """
    GET /api/genomics/output/<output_id>/full/
    يرجع الـ JSON الكامل الجاهز للفرونت: patient + control + binding_proteins
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, output_id):
        import json
        from django.conf import settings
        from .models import OutputData

        try:
            output = OutputData.objects.select_related(
                "input_data__patient", "input_data__cell_type"
            ).get(pk=output_id)
        except OutputData.DoesNotExist:
            return Response({"error": "OutputData not found"}, status=status.HTTP_404_NOT_FOUND)

        def _load_json(field_file):
            if not field_file:
                return None
            abs_path = os.path.join(settings.MEDIA_ROOT, field_file.name)
            if not os.path.exists(abs_path):
                return None
            with open(abs_path, "r", encoding="utf-8") as f:
                return json.load(f)

        patient_struct = _load_json(output.coords_patient_file)
        control_struct = _load_json(output.coords_control_file)

        payload = {
            "patient": patient_struct,
            "control": control_struct,
            "binding_proteins": output.affected_proteins or {},
        }
        return Response(payload, status=status.HTTP_200_OK)
    
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
            # يفضل استخدام select_related لـ OneToOneField إذا كانت العلاقة كذلك لتسريع الاستعلام
            input_data = InputData.objects.select_related("patient", "cell_type", "output").get(pk=input_id)
        except InputData.DoesNotExist:
            return Response({"error": "InputData not found"}, status=status.HTTP_404_NOT_FOUND)

        # تجهيز القيم الافتراضية
        response = {
            "input_data_id": input_data.id,
            "status": input_data.status,
            "patient": input_data.patient.name,
            "chromosome": input_data.chromosome,
            "cell_type": input_data.cell_type.name,
            "created_at": input_data.created_at,
            "output_data_id": None,
            "message": "" # حقل جديد لتوضيح الحالة
        }

        # التحقق من الحالة والبيانات
        output_obj = getattr(input_data, 'output', None)

        if input_data.status == "completed":
            if output_obj:
                response["output_data_id"] = output_obj.id
                response["message"] = "تمت المعالجة بنجاح"
            else:
                response["message"] = "اكتملت الحالة ولكن لا توجد بيانات مخرجات (Output)"
        
        elif input_data.status == "processing" or input_data.status == "pending":
            response["message"] = "جاري العمل في الخلفية..."
            
        elif input_data.status == "failed":
            response["message"] = "فشلت عملية المعالجة في الخلفية" # التعامل مع حالة الفشل هنا
            
        else:
            response["message"] = "لا توجد عمليات معالجة حالياً"
            
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
            from backend.services.genomics.scanning_motifs.protein_search import search_protein_by_gene

            result = search_protein_by_gene(gene)
        except Exception as exc:
            logger.exception("[SearchProtein] lookup failed for gene=%s", gene)
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        if not result:
            return Response({"error": f"No UniProt entry found for gene '{gene}'"}, status=status.HTTP_404_NOT_FOUND)

        return Response(result, status=status.HTTP_200_OK)


from .models import GeneProteinResult
from .serializers import GeneListItemSerializer, GeneDetailSerializer

class GeneListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, output_id):
        genes = GeneProteinResult.objects.filter(output_data_id=output_id)
        return Response(GeneListItemSerializer(genes, many=True).data)


class GeneDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, output_id, gene_id):
        try:
            gene = GeneProteinResult.objects.get(output_data_id=output_id, gene_id=gene_id)
        except GeneProteinResult.DoesNotExist:
            return Response({"error": "Gene not found for this output"}, status=status.HTTP_404_NOT_FOUND)

        data = GeneDetailSerializer(gene).data

        from .models import OutputData
        import json
        output = OutputData.objects.get(pk=output_id)

        def _region_points(field_file):
            if not field_file:
                return []
            abs_path = os.path.join(settings.MEDIA_ROOT, field_file.name)
            if not os.path.exists(abs_path):
                return []
            with open(abs_path, "r", encoding="utf-8") as f:
                coords = json.load(f).get("coords_raw", [])
            points = []
            for point in coords:
                region = point.get("region", "")
                try:
                    start_kb, end_kb = region.replace("kb", "").split("-")
                    p_start = int(start_kb) * 1000
                    p_end = int(end_kb) * 1000
                except (ValueError, AttributeError):
                    continue
                if p_end > gene.gene_start and p_start < gene.gene_end:
                    points.append(point)
            return points

        data["patient_3d_region"] = _region_points(output.coords_patient_file)
        data["control_3d_region"] = _region_points(output.coords_control_file)

        return Response(data)