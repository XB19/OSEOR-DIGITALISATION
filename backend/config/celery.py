"""
Application Celery de la plateforme OSEOR.

Sert les traitements planifiés que l'API ne peut pas porter : acquisition
mensuelle des congés, alertes de seuil de stock, expiration des contrats,
rappels d'événements et d'anniversaires. Le broker est le Redis déjà
présent pour les WebSockets.

Les horaires sont stockés en base (`django-celery-beat`) et modifiables
depuis l'admin Django : un administrateur OSEOR peut décaler un traitement
sans redéploiement.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("oseor")

# Toute la configuration vit dans settings.py, préfixée CELERY_.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Découvre les tasks.py de chaque application installée.
app.autodiscover_tasks()


@app.task(name="config.ping")
def ping():
    """
    Tâche témoin : permet de vérifier qu'un worker répond réellement, sans
    dépendre d'un traitement métier. Utilisée au déploiement et en
    supervision.
    """
    return "pong"
