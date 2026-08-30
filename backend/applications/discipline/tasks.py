"""Tâches planifiées du module Discipline."""

from celery import shared_task

from . import services


@shared_task(name="discipline.alerter_delais")
def alerter_delais():
    """
    Prévient quand le délai de deux mois de l'article 58 approche.

    Passé ce délai plus rien n'est possible : un dossier oublié devient une
    faute impunie, et le salarié reste sous procédure ouverte sans terme.
    """
    return services.alerter_delais()


TACHES_PLANIFIEES = [
    {
        "nom": "Alerte des délais disciplinaires",
        "tache": "discipline.alerter_delais",
        "crontab": {"minute": "0", "hour": "9", "day_of_week": "1"},
        "description": (
            "Chaque lundi à 9h, signale les procédures dont le délai de "
            "sanction de deux mois expire sous quinze jours."
        ),
    },
]
