# Load celery app when Django starts (optional — works without Redis/Celery too)
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    celery_app = None
    __all__ = ()
