from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import *

router = DefaultRouter()
router.register(r'cell-types', CellTypeViewSet, basename='celltype')
router.register(r'', InputDataViewSet, basename='input')

urlpatterns = [
    path("run-test/", RunGenomicTestAPIView.as_view(), name="run-test"),
    
    path("test-status/<int:input_id>/", TestStatusAPIView.as_view(), name="test-status"),
    
    path("search-protein/", SearchProteinAPIView.as_view(), name="search-protein"),

    path("output/<int:output_id>/full/", OutputDataFullDetailAPIView.as_view(), name="output-full-detail"),
    path("output/<int:output_id>/genes/", GeneListAPIView.as_view(), name="genes-list"),
    path("output/<int:output_id>/genes/<str:gene_id>/", GeneDetailAPIView.as_view(), name="gene-detail"),
    
    path('', include(router.urls)),
]
