from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PatientViewSet

router = DefaultRouter()
router.register(r'', PatientViewSet, basename='patient')

urlpatterns = [
    path('', include(router.urls)),
]

# GET    /api/patients/             -> list all patients
# POST   /api/patients/             -> create a new patient
# GET    /api/patients/<id>/        -> retrieve a single patient
# PUT    /api/patients/<id>/        -> replace a patient
# PATCH  /api/patients/<id>/        -> partially update a patient
# DELETE /api/patients/<id>/        -> delete a patient
# GET    /api/patients/<id>/tests/  -> every genomic test (InputData) for this patient
