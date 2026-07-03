from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnalysisReportViewSet,
    RegenerateLLMReportAPIView,
    ReportDetailAPIView,
    ReportUpdateDeleteAPIView,
)

router = DefaultRouter()
router.register(r'', AnalysisReportViewSet, basename='report')

urlpatterns = [
    # Legacy / convenience paths used by the bundled frontend (kept first so
    # they take priority over the router's `<pk>` pattern where they overlap)
    path("<int:output_id>/report/", ReportDetailAPIView.as_view(), name="report-detail-by-output"),
    path("report/<int:report_id>/", ReportUpdateDeleteAPIView.as_view(), name="report-update-delete"),
    path("report/<int:report_id>/regenerate/", RegenerateLLMReportAPIView.as_view(), name="report-regenerate"),

    # Full REST CRUD for AnalysisReport
    path('', include(router.urls)),
]

# GET    /api/reports/                          -> list all reports
# POST   /api/reports/                          -> create a report directly
# GET    /api/reports/<id>/                     -> retrieve a report
# PUT    /api/reports/<id>/                     -> replace a report
# PATCH  /api/reports/<id>/                     -> partially update a report
# DELETE /api/reports/<id>/                     -> delete a report
# POST   /api/reports/<id>/regenerate/          -> re-queue LLM report generation (DRF action)
#
# GET    /api/reports/<output_id>/report/       -> legacy: look up report by OutputData id
# PUT    /api/reports/report/<report_id>/       -> legacy: update report
# DELETE /api/reports/report/<report_id>/       -> legacy: delete report
# POST   /api/reports/report/<report_id>/regenerate/ -> legacy: regenerate report
