"""Tâches planifiées du module Événements."""

from celery import shared_task

from . import services


@shared_task(name="evenements.notifier_anniversaires_du_jour")
def notifier_anniversaires_du_jour():
    """Prévient chaque filiale des anniversaires du jour."""
    return services.notifier_anniversaires_du_jour()


TACHES_PLANIFIEES = [
    {
        "nom": "Anniversaires du jour",
        "tache": "evenements.notifier_anniversaires_du_jour",
        "crontab": {"minute": "30", "hour": "7"},
        "description": (
            "Chaque matin à 7h30, prévient les collègues d'une même filiale "
            "des anniversaires du jour."
        ),
    },
]
