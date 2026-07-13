from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import AnalysisReportViewSet

router = DefaultRouter()
router.register(r'', AnalysisReportViewSet, basename='report')

urlpatterns = [
    # جميع مسارات الـ CRUD والـ Actions المخصصة (regenerate و export-pdf) يتم تضمينها تلقائياً هنا:
    # GET    /api/reports/<id>/             -> لجلب التقرير
    # PUT    /api/reports/<id>/             -> للتعديل الكامل
    # PATCH  /api/reports/<id>/             -> للتعديل الجزئي
    # DELETE /api/reports/<id>/             -> للحذف وتنظيف الديسك
    # POST   /api/reports/<id>/regenerate/  -> لإعادة التوليد عبر السيليري
    # GET    /api/reports/<id>/export-pdf/  -> لتصدير ملف الـ PDF الإنكليزي الفخم
    path('', include(router.urls)),
]
