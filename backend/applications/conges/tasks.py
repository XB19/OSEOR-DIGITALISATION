"""Tâches planifiées du module Congés."""

from celery import shared_task
from django.utils import timezone

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
def expirer_soldes(forcer=False):
    """
    Purge les soldes non pris au 31 décembre (règle RH : jours perdus).

    Refuse d'agir un autre jour, même si l'ordonnanceur la déclenche : une
    planification erronée a déjà programmé cette tâche toutes les nuits, et
    elle aurait vidé le solde de tout le personnel chaque soir. L'opération
    étant destructrice, elle vérifie elle-même la date plutôt que de faire
    confiance à son appelant.

    `forcer=True` permet une clôture manuelle hors du 31 décembre.
    """
    aujourdhui = timezone.localdate()

    if not forcer and (aujourdhui.month, aujourdhui.day) != (12, 31):
        return f"ignoree : {aujourdhui:%d/%m} n'est pas le 31/12"

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
