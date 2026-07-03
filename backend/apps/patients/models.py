from django.db import models
from django.utils import timezone


class Patient(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    mrn = models.CharField(max_length=30, unique=True, verbose_name="Medical Record Number")
    name = models.CharField(max_length=150, verbose_name="Full Name")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name="Gender")
    dob = models.DateField(default=timezone.now, verbose_name="Date of Birth")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.mrn})"

    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patients"
        ordering = ['-created_at']
