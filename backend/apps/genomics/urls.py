from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CellTypeViewSet,
    InputDataViewSet,
    RunGenomicTestAPIView,
    TestStatusAPIView,
    SearchProteinAPIView,  
)

router = DefaultRouter()
router.register(r'cell-types', CellTypeViewSet, basename='celltype')
router.register(r'', InputDataViewSet, basename='input')

urlpatterns = [
    path("run-test/", RunGenomicTestAPIView.as_view(), name="run-test"),
    
    path("test-status/<int:input_id>/", TestStatusAPIView.as_view(), name="test-status"),
    
    path("search-protein/", SearchProteinAPIView.as_view(), name="search-protein"),
    
    path('', include(router.urls)),
]
