from django.shortcuts import render

# Create your views here.
"""
apps/proteomics/views.py
"""

import logging
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import ProteinInputData, ProteinOutputData
from .serializers import (
    ProteinInputDataListSerializer,
    ProteinInputDataDetailSerializer,
    ProteinInputDataCreateSerializer,
    ProteinOutputDataSerializer,
    TestStatusSerializer,
)
from .tasks import run_protein_pipeline_task

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# POST /api/proteomics/run-test/
# ─────────────────────────────────────────────────────────────────────────
class RunProteinTestAPIView(generics.CreateAPIView):
    """
    يستقبل ملف FASTA (وربما ملف control اختياري)، ينشئ سجل ProteinInputData
    جديد بحالة PENDING، ثم يطلق مهمة Celery فوراً بالخلفية.
    """

    queryset = ProteinInputData.objects.all()
    serializer_class = ProteinInputDataCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        input_data = serializer.save(status=ProteinInputData.Status.PENDING)
        run_protein_pipeline_task.delay(input_data.id)
        self._created_instance = input_data

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # نرجع نسخة القائمة المختصرة (فيها status) بدل الاعتماد على الافتراضي
        response.data = ProteinInputDataListSerializer(
            self._created_instance
        ).data
        return response


# ─────────────────────────────────────────────────────────────────────────
# GET /api/proteomics/test-status/<id>/
# ─────────────────────────────────────────────────────────────────────────
class TestStatusAPIView(generics.RetrieveAPIView):
    """Endpoint خفيف مخصص لعمليات الـ polling المتكررة من الفرونت إند."""

    queryset = ProteinInputData.objects.all()
    serializer_class = TestStatusSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "id"


# ─────────────────────────────────────────────────────────────────────────
# GET /api/proteomics/                 (قائمة، مع فلترة patient_id)
# GET /api/proteomics/<id>/            (تفاصيل مدموجة input + output)
# DELETE /api/proteomics/<id>/
# ─────────────────────────────────────────────────────────────────────────
class ProteinInputDataListView(generics.ListAPIView):
    serializer_class = ProteinInputDataListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ProteinInputData.objects.all()
        patient_id = self.request.query_params.get("patient_id")
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        return queryset


class ProteinInputDataDetailView(generics.RetrieveDestroyAPIView):
    queryset = ProteinInputData.objects.select_related("output_data").all()
    serializer_class = ProteinInputDataDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "id"


# ─────────────────────────────────────────────────────────────────────────
# POST /api/proteomics/<id>/stop/
# ─────────────────────────────────────────────────────────────────────────
class StopProteinTestAPIView(APIView):
    """
    يضبط الحالة إلى CANCELLING فقط - المهمة نفسها (tasks.py) هي المسؤولة
    عن قراءة هذه الحالة بين كل خطوة وأخرى وإيقاف نفسها فعلياً (Cooperative
    Cancellation)، بدل قتل الـ task بالقوة (وهو أسلوب غير آمن مع Celery).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        input_data = get_object_or_404(ProteinInputData, pk=id)

        if input_data.status in (
            ProteinInputData.Status.COMPLETED,
            ProteinInputData.Status.FAILED,
            ProteinInputData.Status.CANCELLED,
        ):
            return Response(
                {"error": f"لا يمكن إيقاف تحليل بحالة '{input_data.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        input_data.status = ProteinInputData.Status.CANCELLING
        input_data.save(update_fields=["status"])
        return Response(TestStatusSerializer(input_data).data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────
# POST /api/proteomics/<id>/retry/
# ─────────────────────────────────────────────────────────────────────────
class RetryProteinTestAPIView(APIView):
    """
    يعيد تشغيل الـ pipeline من الصفر لتحليل فاشل أو ملغى. لا يُنشئ سجلاً
    جديداً - يعيد استخدام نفس ProteinInputData بعد حذف أي ProteinOutputData
    قديم مرتبط به (لأن العلاقة OneToOne لا تسمح بأكثر من سجل واحد).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        input_data = get_object_or_404(ProteinInputData, pk=id)

        if input_data.status not in (
            ProteinInputData.Status.FAILED,
            ProteinInputData.Status.CANCELLED,
        ):
            return Response(
                {"error": "لا يمكن إعادة المحاولة إلا لتحليل فاشل أو ملغى."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # حذف الناتج القديم إن وجد، لأن الـ pipeline سينشئ ناتجاً جديداً بالكامل
        ProteinOutputData.objects.filter(input_data=input_data).delete()

        input_data.status = ProteinInputData.Status.PENDING
        input_data.save(update_fields=["status"])

        run_protein_pipeline_task.delay(input_data.id)
        return Response(TestStatusSerializer(input_data).data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────
# GET /api/proteomics/output/<output_id>/full/
# ─────────────────────────────────────────────────────────────────────────
class ProteinOutputFullDetailAPIView(generics.RetrieveAPIView):
    """
    الـ JSON الكامل (بنية + مقارنة + إحصائيات) - endpoint منفصل عن تفاصيل
    الـ input لأن الفرونت إند غالباً بيحتاجه لوحده لعرض صفحة النتائج
    (structure viewer + جدول الطفرات) دون الحاجة لبيانات الـ input الإدارية.
    """

    queryset = ProteinOutputData.objects.all()
    serializer_class = ProteinOutputDataSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "output_id"