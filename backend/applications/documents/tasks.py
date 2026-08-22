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


# Déclaration reprise par `manage.py seed_taches_planifiees`.
TACHES_PLANIFIEES = [
    {
        "nom": "Relance des documents en attente de visa",
        "tache": "documents.rappeler_documents_en_attente",
        "crontab": {"minute": "0", "hour": "8", "day_of_week": "1-5"},
        "kwargs": {"seuil_jours": 3},
        "description": (
            "Chaque matin ouvré à 8h, renotifie les visas dormants depuis "
            "plus de 3 jours."
        ),
    },
]
