"""
core/celery.py
إعداد Celery للمشروع — يُستورَد من core/__init__.py
"""

import os

from celery import Celery

# تحديد ملف الإعدادات الافتراضي لـ Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("genomic_project")

# تحميل الإعدادات من Django settings تحت مفتاح CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# الاكتشاف التلقائي لملفات tasks.py في كل تطبيق
app.autodiscover_tasks()


# ─────────────────────────────────────────────────────────────────────────────
# core/__init__.py  — تأكد من وجود هذا السطر
# ─────────────────────────────────────────────────────────────────────────────
# from .celery import app as celery_app
# __all__ = ("celery_app",)


# ─────────────────────────────────────────────────────────────────────────────
# تشغيل Celery Worker (في Terminal منفصل)
# ─────────────────────────────────────────────────────────────────────────────
"""
# تشغيل Redis أولاً (لو مش شغال)
redis-server

# تشغيل الـ Worker
celery -A core worker --loglevel=info --concurrency=2

# لمراقبة المهام (اختياري)
celery -A core flower
"""