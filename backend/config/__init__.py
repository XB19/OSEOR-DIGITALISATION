# Rend l'application Celery disponible dès le chargement de Django, pour que
# le décorateur @shared_task des modules tasks.py s'y rattache.
from .celery import app as celery_app

__all__ = ("celery_app",)
