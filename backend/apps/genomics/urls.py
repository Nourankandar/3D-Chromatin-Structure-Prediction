"""
apps/genomics/urls.py
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CellTypeViewSet,
    GetVisualizationDataAPIView,
    InputDataViewSet,
    OutputDataViewSet,
    RunGenomicTestAPIView,
    SearchProteinAPIView,
    TestStatusAPIView,
)

router = DefaultRouter()
router.register(r'cell-types', CellTypeViewSet, basename='celltype')
router.register(r'outputs', OutputDataViewSet, basename='output')
# InputData ("tests") registered at the router root so the resource lives at
# /api/genomics/  (and is also mounted at /api/tests/ — see core/urls.py)
router.register(r'', InputDataViewSet, basename='input')

urlpatterns = [
    path("run-test/", RunGenomicTestAPIView.as_view(), name="run-test"),
    path("test-status/<int:input_id>/", TestStatusAPIView.as_view(), name="test-status"),
    path("visualization-data/<int:output_id>/", GetVisualizationDataAPIView.as_view(), name="visualization-data"),
    path("search-protein/", SearchProteinAPIView.as_view(), name="search-protein"),
    path('', include(router.urls)),
]

# GET    /api/genomics/cell-types/                  -> list cell types ({"cell_types": [...]})
# POST   /api/genomics/cell-types/                  -> create a cell type
# GET    /api/genomics/cell-types/<id>/              -> retrieve a cell type
# PUT    /api/genomics/cell-types/<id>/              -> replace a cell type
# PATCH  /api/genomics/cell-types/<id>/              -> partially update a cell type
# DELETE /api/genomics/cell-types/<id>/              -> delete a cell type
#
# GET    /api/genomics/outputs/                      -> list pipeline outputs (read-only)
# GET    /api/genomics/outputs/<id>/                 -> retrieve a pipeline output (read-only)
#
# GET    /api/genomics/                              -> list genomic tests (InputData)
# POST   /api/genomics/                              -> create a genomic test record directly
# GET    /api/genomics/<id>/                         -> retrieve a genomic test
# PUT    /api/genomics/<id>/                          -> replace a genomic test
# PATCH  /api/genomics/<id>/                          -> partially update a genomic test
# DELETE /api/genomics/<id>/                          -> delete a genomic test
#
# POST   /api/genomics/run-test/                     -> upload FASTA + queue the prediction pipeline
# GET    /api/genomics/test-status/<input_id>/        -> poll pipeline status
# GET    /api/genomics/visualization-data/<output_id>/ -> assembled URLs for the 3D viewer
# GET    /api/genomics/search-protein/?gene=<symbol>  -> UniProt/PDB lookup by gene symbol
