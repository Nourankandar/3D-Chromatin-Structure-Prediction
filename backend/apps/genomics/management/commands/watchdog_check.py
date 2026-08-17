"""
apps/genomics/management/commands/watchdog_check.py
====================================================================
يفحص لو في تحليل "عالق" (status شغال بس ما تحرك منذ فترة طويلة)،
ولو لقى، بيقتل عملية Celery worker، يفضي الطابور، يفشّل التحليل
العالق بالداتابيز، وبيعيد تشغيل Celery من جديد تلقائياً.
====================================================================
"""
import subprocess
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

STALE_THRESHOLD_MINUTES = 25  

ACTIVE_STATUSES = [
    'pending', 'predicting_dnase', 'generating_hic',
    'generating_hic_coords', 'scanning_motifs', 'cancelling',
]


class Command(BaseCommand):
    help = "يفحص التحاليل العالقة ويعيد تشغيل Celery تلقائياً لو لزم."

    def handle(self, *args, **options):
        from apps.genomics.models import InputData

        cutoff = timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES)
        stuck = InputData.objects.filter(status__in=ACTIVE_STATUSES, updated_at__lt=cutoff)

        if not stuck.exists():
            self.stdout.write("[Watchdog] لا يوجد تحليل عالق.")
            return

        for input_data in stuck:
            self.stdout.write(
                f"[Watchdog] تحليل عالق مكتشف: InputData id={input_data.id} "
                f"(status={input_data.status}, آخر تحديث={input_data.updated_at})"
            )

        try:
            from core.celery import app
            app.control.purge()
            self.stdout.write("[Watchdog] تم تفضية طابور Celery.")
        except Exception as exc:
            self.stdout.write(f"[Watchdog] تحذير: فشلت تفضية الطابور: {exc}")

        subprocess.run(
            'taskkill /FI "WINDOWTITLE eq Celery Worker*" /F',
            shell=True, capture_output=True,
        )
        self.stdout.write("[Watchdog] تم إيقاف عملية Celery worker العالقة.")

        updated_count = stuck.update(status="failed", updated_at=timezone.now())
        self.stdout.write(f"[Watchdog] تم تحديث {updated_count} تحليل إلى status=failed.")

        time.sleep(2)
        subprocess.Popen(
            'start "Celery Worker" /min .env\\Scripts\\python.exe -m celery -A core worker -l info --pool=solo',
            shell=True,
        )
        self.stdout.write("[Watchdog] تم إعادة تشغيل Celery worker.")