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
from backend.core.utils.atomic_utils import atomic_with_cleanup
from django.template.loader import render_to_string
import markdown as md_lib
import re

def _markdown_to_html(raw_text: str) -> str:
    if not raw_text:
        return ""

    text = raw_text.strip()
    fence_match = re.search(r'```(?:markdown)?\s*\n(.*?)\n?```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        text = re.sub(r'^```(?:markdown)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)

    return md_lib.markdown(
        text.strip(),
        extensions=['tables', 'fenced_code', 'nl2br']
    )
class AnalysisReportViewSet(
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    viewsets.GenericViewSet
):
    """
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

        input_data = report.output_data.input_data
        if input_data.status in ["pending", "processing"]:
            return Response(
                {"error": "Cannot regenerate report while the genomic pipeline is still running."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_status = report.status
        old_summary = report.summary_text

        def rollback_report_state():
            report.status = old_status
            report.summary_text = old_summary
            report.save(update_fields=["status", "summary_text"])

        try:
            with atomic_with_cleanup(cleanup_fn=rollback_report_state, log_prefix="ReportRegenerate"):
                report.status = "generating"
                report.summary_text = "AI clinical engine is regenerating chromatin folds analysis..."
                report.save(update_fields=["status", "summary_text"])

                from apps.genomics.tasks import generate_llm_report_task
                generate_llm_report_task.delay(report.output_data_id)
        except Exception as exc:
            return Response(
                {"error": f"Failed to queue report regeneration: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
        
        if report.status != "completed" or not report.summary_text:
            return Response(
                {"error": "The clinical report is not ready or still generating. PDF export aborted."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        output_data = report.output_data
        input_data = output_data.input_data

        patient_name = (
            input_data.patient.name
            if hasattr(input_data, 'patient') and input_data.patient
            else "N/A"
        )

        context = {
            "patient_name": patient_name,
            "patient_code": f"PT-2026-{input_data.patient.id}" if hasattr(input_data, 'patient') and input_data.patient else "N/A",
            "cell_type_name": input_data.cell_type.name if hasattr(input_data, 'cell_type') and input_data.cell_type else "N/A",
            "analysis_date": report.created_at.strftime('%B %d, %Y'),
            "output_id": output_data.id,
            "detected_disease": report.detected_disease if report.detected_disease else "No significant structural variation detected.",
            "summary_text": _markdown_to_html(report.summary_text),
        }
        
        html_string = render_to_string("medical_report_pdf.html", context)
        
        safe_patient_name = re.sub(r'[^A-Za-z0-9_-]+', '_', patient_name.strip()) if patient_name and patient_name != "N/A" else f"Output_{output_data.id}"
        safe_patient_name = safe_patient_name.strip('_') or f"Output_{output_data.id}"
        report_date = report.created_at.strftime('%Y-%m-%d')
        filename = f"Clinical_Report_{safe_patient_name}_{report_date}.pdf"

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename={filename}"
        
        HTML(string=html_string).write_pdf(response)
        return response