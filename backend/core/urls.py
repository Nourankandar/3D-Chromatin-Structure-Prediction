"""
core/urls.py
Root URL configuration for the 3D Chromatin Structure Prediction backend.

API layout:
    /api/auth/                        -> apps.accounts  (signup / login / logout / token refresh)
    /api/patients/                     -> apps.patients  (Patient CRUD)
    /api/genomics/cell-types/          -> apps.genomics  (CellType CRUD)
    /api/genomics/                     -> apps.genomics  (InputData CRUD)
    /api/genomics/outputs/             -> apps.genomics  (OutputData, read-only)
    /api/genomics/run-test/            -> apps.genomics  (kick off the pipeline)
    /api/genomics/test-status/<id>/    -> apps.genomics
    /api/genomics/visualization-data/<id>/ -> apps.genomics
    /api/genomics/search-protein/      -> apps.genomics
    /api/reports/                      -> apps.reports   (AnalysisReport CRUD + regenerate)

    /api/tests/  is kept as an alias of /api/genomics/ — the bundled
    frontend (frontend/js/dashboard_v3.js) was built against that path
    (e.g. POST /api/tests/, GET /api/tests/cell-types/), so both prefixes
    are wired to the exact same urlconf to avoid breaking it.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView


urlpatterns = [
    path('admin/', admin.site.urls),

    path('', TemplateView.as_view(template_name='index.html')),
    path('login.html', TemplateView.as_view(template_name='login.html')),
    path('dashboard.html', TemplateView.as_view(template_name='dashboard.html')),
    path('viewer.html', TemplateView.as_view(template_name='viewer.html')),
    path('hic_viewer.html', TemplateView.as_view(template_name='hic_viewer.html')),
    path('protein_viewer.html', TemplateView.as_view(template_name='protein_viewer.html')),

    path('api/patients/', include('apps.patients.urls')),
    path('api/genomics/', include('apps.genomics.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/proteomics/', include('apps.proteomics.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

