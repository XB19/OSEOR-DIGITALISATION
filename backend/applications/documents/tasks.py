"""
Tâches planifiées du module Documents.

Convention du projet : la logique vit dans `services.py` (testable sans
Celery, appelable depuis une commande de gestion), la tâche n'est qu'une
enveloppe. Les modules à venir — congés, événements — suivent ce découpage.
"""

from celery import shared_task

from . import services


@shared_task(name="documents.rappeler_documents_en_attente")
def rappeler_documents_en_attente(seuil_jours=3):
    """Relance les documents dont le visa dort depuis trop longtemps."""
    return services.rappeler_documents_en_attente(seuil_jours=seuil_jours)
