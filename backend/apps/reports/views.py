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

from .models import AnalysisReport
from .serializers import AnalysisReportSerializer


class AnalysisReportViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for AnalysisReport.

    GET    /api/reports/                  -> list all reports
    POST   /api/reports/                  -> create a report directly
    GET    /api/reports/<id>/             -> retrieve a report
    PUT    /api/reports/<id>/             -> replace a report
    PATCH  /api/reports/<id>/             -> partially update a report
    DELETE /api/reports/<id>/             -> delete a report
    POST   /api/reports/<id>/regenerate/  -> re-queue the LLM report generation task
    """

    queryset = AnalysisReport.objects.select_related(
        "output_data__input_data__patient", "output_data__input_data__cell_type"
    ).all()
    serializer_class = AnalysisReportSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['detected_disease', 'status']
    ordering_fields = ['created_at', 'updated_at', 'status']

    @action(detail=True, methods=["post"], url_path="regenerate")
    def regenerate(self, request, pk=None):
        report = self.get_object()

        from apps.genomics.tasks import generate_llm_report_task

        generate_llm_report_task.delay(report.output_data_id)

        return Response(
            {
                "message": "Report regeneration queued",
                "report_id": report.id,
                "output_data_id": report.output_data_id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Legacy endpoints, kept for the bundled frontend which calls these directly
# by output_id rather than report id.
# ─────────────────────────────────────────────────────────────────────────────
class ReportDetailAPIView(APIView):
    """GET /api/reports/<output_id>/report/ — look up a report by its OutputData id."""

    permission_classes = [IsAuthenticated]

    def get(self, request, output_id):
        try:
            report = AnalysisReport.objects.select_related("output_data").get(output_data_id=output_id)
        except AnalysisReport.DoesNotExist:
            return Response({"error": "Report not found for this output"}, status=status.HTTP_404_NOT_FOUND)

        return Response(AnalysisReportSerializer(report).data, status=status.HTTP_200_OK)


class ReportUpdateDeleteAPIView(APIView):
    """PUT/DELETE /api/reports/report/<report_id>/"""

    permission_classes = [IsAuthenticated]

    def _get_report(self, report_id):
        try:
            return AnalysisReport.objects.get(pk=report_id)
        except AnalysisReport.DoesNotExist:
            return None

    def put(self, request, report_id):
        report = self._get_report(report_id)
        if not report:
            return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AnalysisReportSerializer(report, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, report_id):
        report = self._get_report(report_id)
        if not report:
            return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)

        report.delete()
        return Response({"message": "Report deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class RegenerateLLMReportAPIView(APIView):
    """POST /api/reports/report/<report_id>/regenerate/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, report_id):
        try:
            report = AnalysisReport.objects.select_related("output_data").get(pk=report_id)
        except AnalysisReport.DoesNotExist:
            return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)

        from apps.genomics.tasks import generate_llm_report_task

        generate_llm_report_task.delay(report.output_data_id)

        return Response(
            {
                "message": "Report regeneration queued",
                "report_id": report.id,
                "output_data_id": report.output_data_id,
            },
            status=status.HTTP_202_ACCEPTED,
        )
