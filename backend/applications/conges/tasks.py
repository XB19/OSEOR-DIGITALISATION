"""Tâches planifiées du module Congés."""

from celery import shared_task
from django.conf import settings
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
def expirer_soldes(annee=None, forcer=False):
    """
    Purge les soldes d'une année révolue.

    **Inactive par défaut** : les congés se cumulent sans limite de temps
    (décision OSEOR), cette tâche n'est plus planifiée. Elle subsiste pour
    le jour où le groupe appliquerait le plafond légal de report de deux
    ans (Code du travail togolais, art. 200 à 202) — il suffira alors de
    renseigner `CONGES_REPORT_MAX_ANNEES` et de replanifier.

    L'opération étant destructrice, elle refuse d'agir tant qu'aucun
    plafond n'est configuré, et vérifie elle-même la date plutôt que de
    faire confiance à son ordonnanceur : une planification erronée a déjà
    programmé cette tâche toutes les nuits, ce qui aurait vidé le solde de
    tout le personnel chaque soir.
    """
    plafond = getattr(settings, "CONGES_REPORT_MAX_ANNEES", None)

    if plafond is None and not forcer:
        return ("ignoree : les conges se cumulent sans limite "
                "(CONGES_REPORT_MAX_ANNEES non defini)")

    aujourdhui = timezone.localdate()

    if not forcer and (aujourdhui.month, aujourdhui.day) != (12, 31):
        return f"ignoree : {aujourdhui:%d/%m} n'est pas le 31/12"

    if annee is None:
        annee = aujourdhui.year - (plafond or 0)

    return str(services.expirer_tous_les_soldes(annee))


@shared_task(name="conges.rappeler_departs")
def rappeler_departs():
    """Rappelle la veille aux salariés dont le congé commence demain."""
    return services.rappeler_departs_imminents()


TACHES_PLANIFIEES = [
    {
        "nom": "Rappel des départs en congé",
        "tache": "conges.rappeler_departs",
        "crontab": {"minute": "0", "hour": "16"},
        "description": (
            "Chaque jour à 16h, prévient le salarié, son valideur et les "
            "RH d'un départ en congé le lendemain."
        ),
    },
    {
        "nom": "Acquisition mensuelle des congés",
        "tache": "conges.crediter_acquisitions",
        "crontab": {"minute": "0", "hour": "1"},
        "description": (
            "Chaque nuit à 1h, crédite 2,5 jours aux salariés dont un mois "
            "de service vient d'être révolu."
        ),
    },
    # Pas de tâche d'expiration : les congés se cumulent sans limite de
    # temps. `conges.expirer_soldes` reste disponible pour une exécution
    # manuelle si le plafond légal de report venait à être appliqué.
]
