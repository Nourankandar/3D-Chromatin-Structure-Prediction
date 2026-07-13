"""
apps/reports/views.py
REST endpoints for AI-generated clinical reports.

Includes a full ModelViewSet (list/create/retrieve/update/delete) plus the
original purpose-built endpoints (lookup-by-output, regenerate) kept for
backward compatibility with the bundled frontend.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin
from .models import AnalysisReport
from .serializers import AnalysisReportSerializer
from weasyprint import HTML
from django.http import HttpResponse
from django.template.loader import render_to_string

class AnalysisReportViewSet(
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    viewsets.GenericViewSet
):
    """
    إدارة التقرير الطبي الخاص بكل تحليل (علاقة رأس لراس فقط).
    تم إلغاء القوائم (List) والإنشاء المباشر (Create).
    
    GET    /api/reports/<id>/     -> جلب نص التقرير الخاص بهذا التحليل
    PUT    /api/reports/<id>/     -> تعديل نص التقرير يدوياً من قبل الطبيب
    PATCH  /api/reports/<id>/     -> تعديل جزئي للتقرير
    DELETE /api/reports/<id>/     -> حذف التقرير
    POST   /api/reports/<id>/regenerate/ -> إعادة إرسال طلب توليد التقرير للسيليري بالخلفية
    """

    queryset = AnalysisReport.objects.select_related(
        "output_data__input_data__patient", "output_data__input_data__cell_type"
    ).all()
    serializer_class = AnalysisReportSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"], url_path="regenerate")
    def regenerate(self, request, pk=None):
        report = self.get_object()

        # حارس الأمان: نتحقق من حالة التحليل الأساسي (InputData) المرتبط بهذا التقرير
        input_data = report.output_data.input_data
        if input_data.status in ["pending", "processing"]:
            return Response(
                {
                    "error": "Cannot regenerate report while the genomic pipeline is still running."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. نقلب حالة التقرير في الداتا فوراً ليعرض الفرونت إند مؤشر التحميل
        report.status = "generating"
        report.summary_text = "AI clinical engine is regenerating chromatin folds analysis..."
        report.save(update_fields=["status", "summary_text"])

        # 2. نرسل المهمة للسيليري بأمان لأننا تأكدنا أن المسار السابق منتهي
        from apps.genomics.tasks import generate_llm_report_task
        generate_llm_report_task.delay(report.output_data_id)

        return Response(
            {
                "message": "Report regeneration queued successfully.",
                "report_id": report.id,
                "status": "generating"
            },
            status=status.HTTP_202_ACCEPTED,
        )
    
    @action(detail=True, methods=["get"], url_path="export-pdf")
    def export_pdf(self, request, pk=None):
        """
        Exports the clinical analysis report as a high-fidelity, professional English PDF.
        The HTML template is separated into an external file to maintain clean code architecture.
        """
        report = self.get_object()
        
        # حارس أمان للتأكد من اكتمال التقرير
        if report.status != "completed" or not report.summary_text:
            return Response(
                {"error": "The clinical report is not ready or still generating. PDF export aborted."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        output_data = report.output_data
        input_data = output_data.input_data
        
        # تحضير قاموس البيانات (Context) المترجم للإنكليزية لتمريره إلى القالب
        context = {
            "patient_name": input_data.patient.name if hasattr(input_data, 'patient') and input_data.patient else "N/A",
            "patient_code": f"PT-2026-{input_data.patient.id}" if hasattr(input_data, 'patient') and input_data.patient else "N/A",
            "cell_type_name": input_data.cell_type.name if hasattr(input_data, 'cell_type') and input_data.cell_type else "N/A",
            "analysis_date": report.created_at.strftime('%B %d, %Y'),
            "output_id": output_data.id,
            "detected_disease": report.detected_disease if report.detected_disease else "No significant structural variation detected.",
            "summary_text": report.summary_text
        }
        
        # 1. قراءة الـ HTML الخارجي من مجلد الـ templates ودمجه بالبيانات
        html_string = render_to_string("genomics/medical_report_pdf.html", context)
        
        # 2. إنشاء الـ HTTP Response المخصص لملفات الـ PDF وتحويله عبر WeasyPrint
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename=Clinical_Report_Output_{output_data.id}.pdf"
        
        HTML(string=html_string).write_pdf(response)
        return response