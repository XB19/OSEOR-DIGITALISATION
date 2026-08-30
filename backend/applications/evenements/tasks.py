"""Tâches planifiées du module Événements."""

from celery import shared_task

from . import services


@shared_task(name="evenements.notifier_anniversaires_du_jour")
def notifier_anniversaires_du_jour():
    """Prévient chaque filiale des anniversaires du jour."""
    return services.notifier_anniversaires(dans_jours=0)


@shared_task(name="evenements.rappeler_anniversaires_demain")
def rappeler_anniversaires_demain():
    """Annonce la veille les anniversaires du lendemain."""
    return services.notifier_anniversaires(dans_jours=1)


TACHES_PLANIFIEES = [
    {
        "nom": "Rappel des anniversaires du lendemain",
        "tache": "evenements.rappeler_anniversaires_demain",
        "crontab": {"minute": "0", "hour": "16"},
        "description": (
            "Chaque jour à 16h, annonce les anniversaires du lendemain — le "
            "temps de s'organiser."
        ),
    },
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
