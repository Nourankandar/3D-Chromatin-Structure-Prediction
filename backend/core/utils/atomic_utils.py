"""
core/utils/atomic_utils.py
====================================================================
أداة موحّدة لتغليف عمليات الداتابيز + الموارد الخارجية (ملفات،
استدعاءات Celery، إلخ) بحيث لو صار أي خطأ، يترجع كل شي بالداتابيز
(rollback) وينحذف/ينضف أي مورد خارجي انعمل قبل الخطأ.
====================================================================
"""

import logging
from contextlib import contextmanager

from django.db import transaction

logger = logging.getLogger(__name__)


@contextmanager
def atomic_with_cleanup(cleanup_fn=None, log_prefix="Atomic operation"):
    """
    Context manager يلف عملية بـ transaction.atomic()، وبنفس الوقت
    بيسمح بتنظيف موارد خارج الداتابيز (ملفات، cache، إلخ) لو صار خطأ.

    Usage:
        def cleanup():
            if os.path.exists(some_path):
                os.remove(some_path)

        with atomic_with_cleanup(cleanup_fn=cleanup, log_prefix="RunGenomicTest"):
            obj = Model.objects.create(...)
            some_external_call(obj.id)
    """
    try:
        with transaction.atomic():
            yield
    except Exception:
        logger.exception("[%s] Failed — rolled back DB changes.", log_prefix)
        if cleanup_fn:
            try:
                cleanup_fn()
            except Exception:
                logger.warning("[%s] Cleanup function itself failed.", log_prefix)
        raise