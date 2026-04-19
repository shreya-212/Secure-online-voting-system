"""Celery configuration for Home project."""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Home.settings')

try:
    from celery import Celery

    app = Celery('Home')
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks()

    @app.task(bind=True, ignore_result=True)
    def debug_task(self):
        print(f'Request: {self.request!r}')

except ImportError:
    app = None
