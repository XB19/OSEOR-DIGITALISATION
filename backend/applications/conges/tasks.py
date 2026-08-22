"""Tâches planifiées du module Congés."""

from celery import shared_task

from . import services


@shared_task(name="conges.crediter_acquisitions")
def crediter_acquisitions():
    """
    Acquisition mensuelle : 2,5 jours par mois de service révolu.

    Tourne chaque jour et non chaque mois : les échéances tombent à la date
    d'anniversaire d'embauche, donc à un jour différent pour chaque
    salarié. La tâche ne crédite que les échéances échues et non encore
    enregistrées, un passage quotidien est donc sans effet la plupart du
    temps.
    """
    return services.crediter_toutes_les_acquisitions()


@shared_task(name="conges.expirer_soldes")
def expirer_soldes():
    """Purge les soldes non pris au 31 décembre (règle RH : jours perdus)."""
    return str(services.expirer_tous_les_soldes())


TACHES_PLANIFIEES = [
    {
        "nom": "Acquisition mensuelle des congés",
        "tache": "conges.crediter_acquisitions",
        "crontab": {"minute": "0", "hour": "1"},
        "description": (
            "Chaque nuit à 1h, crédite 2,5 jours aux salariés dont un mois "
            "de service vient d'être révolu."
        ),
    },
    {
        "nom": "Expiration des soldes de congés",
        "tache": "conges.expirer_soldes",
        "crontab": {"minute": "30", "hour": "23", "day_of_month": "31",
                    "month_of_year": "12"},
        "description": (
            "Le 31 décembre à 23h30, solde les jours non pris — ils sont "
            "perdus."
        ),
    },
]
