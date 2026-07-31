"""
apps/proteomics/urls.py
"""

from django.urls import path
from .views import (
    RunProteinTestAPIView,
    TestStatusAPIView,
    ProteinInputDataListView,
    ProteinInputDataDetailView,
    StopProteinTestAPIView,
    RetryProteinTestAPIView,
    ProteinOutputFullDetailAPIView,
)

app_name = "proteomics"

urlpatterns = [
    path("run-test/", RunProteinTestAPIView.as_view(), name="run-test"),
    path("test-status/<int:id>/", TestStatusAPIView.as_view(), name="test-status"),
    path("", ProteinInputDataListView.as_view(), name="list"),
    path("<int:id>/", ProteinInputDataDetailView.as_view(), name="detail"),
    path("<int:id>/stop/", StopProteinTestAPIView.as_view(), name="stop"),
    path("<int:id>/retry/", RetryProteinTestAPIView.as_view(), name="retry"),
    path(
        "output/<int:output_id>/full/",
        ProteinOutputFullDetailAPIView.as_view(),
        name="output-full",
    ),
]