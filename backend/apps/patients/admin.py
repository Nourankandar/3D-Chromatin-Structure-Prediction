from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['id', 'mrn', 'name', 'gender', 'dob', 'created_at']
    search_fields = ['mrn', 'name']
    list_filter = ['gender']
