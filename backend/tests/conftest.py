"""
tests/conftest.py

كل الملفات بـ services/ عندها `from django.conf import settings` على مستوى
الموديول، فلازم Django يكون مهيأ (configured) قبل ما نستورد أي test module.

انسخ هاد الملف لجذر مشروع backend/ (جنب manage.py)، وشغّل التيستات من هناك:

    cd backend/
    pytest tests/ -v

لو عندك pytest-django مثبت، بديل أبسط: ضيف بملف pytest.ini أو setup.cfg:

    [pytest]
    DJANGO_SETTINGS_MODULE = core.settings   # عدّل حسب اسم settings module عندك

وبعدين شغّل: pytest --ds=core.settings tests/ -v
"""
import os
import django
from django.conf import settings as django_settings

if not django_settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")  # عدّل الاسم حسب مشروعك
    django.setup()
