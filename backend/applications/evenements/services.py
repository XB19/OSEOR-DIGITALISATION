"""
Périmètre de visibilité des événements, et calendrier unifié.

Le calendrier mélange deux sources de nature différente : les événements
saisis (table `Evenement`) et les anniversaires, qui sont **calculés** à
partir de `Utilisateur.date_naissance`. Les anniversaires ne sont jamais
stockés : les matérialiser reviendrait à créer chaque année autant de
lignes que d'employés, et à les désynchroniser dès qu'une date de
naissance est corrigée.
"""

from calendar import isleap
from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Q

from config.permissions import est_direction

from .models import Evenement

User = get_user_model()


def evenements_visibles(utilisateur):
    """
    Événements que `utilisateur` a le droit de voir :

    - direction : tout le groupe ;
    - visibilité GROUPE : tout le monde ;
    - visibilité FILIALE : les membres de la filiale concernée ;
    - visibilité SERVICE : les membres du service concerné.

    Un compte sans filiale ne voit que les événements de groupe.
    """
    queryset = Evenement.objects.select_related(
        "filiale", "service", "salle", "createur")

    if est_direction(utilisateur):
        return queryset

    if not (utilisateur and utilisateur.is_authenticated):
        return queryset.none()

    perimetre = Q(visibilite=Evenement.Visibilite.GROUPE)

    if getattr(utilisateur, "filiale_id", None) is not None:
        perimetre |= Q(
            visibilite=Evenement.Visibilite.FILIALE,
            filiale_id=utilisateur.filiale_id,
        )

    if getattr(utilisateur, "service_id", None) is not None:
        perimetre |= Q(
            visibilite=Evenement.Visibilite.SERVICE,
            service_id=utilisateur.service_id,
        )

    return queryset.filter(perimetre)


def _occurrence_anniversaire(naissance, annee):
    """
    Date de célébration d'un anniversaire pour une année donnée.

    Un 29 février est célébré le 28 les années non bissextiles : ne rien
    renvoyer priverait la personne d'anniversaire trois années sur quatre.
    Convention à confirmer avec les RH — c'est le seul endroit à changer.
    """
    if naissance.month == 2 and naissance.day == 29 and not isleap(annee):
        return date(annee, 2, 28)
    return date(annee, naissance.month, naissance.day)


def anniversaires(debut, fin, utilisateur):
    """
    Anniversaires tombant entre `debut` et `fin` (dates incluses), parmi
    les collègues visibles par `utilisateur` : sa filiale, ou tout le
    groupe pour la direction.

    Renvoie des dictionnaires, pas des `Evenement` : ces occurrences n'ont
    pas d'existence en base et ne doivent pas prétendre le contraire.

    L'âge n'est volontairement pas exposé : souhaiter un anniversaire ne
    demande pas de connaître l'année de naissance de ses collègues.
    """
    if debut > fin:
        return []

    collegues = User.objects.filter(is_active=True, date_naissance__isnull=False)

    if not est_direction(utilisateur):
        filiale_id = getattr(utilisateur, "filiale_id", None)
        if filiale_id is None:
            return []
        collegues = collegues.filter(filiale_id=filiale_id)

    occurrences = []
    for collegue in collegues.select_related("filiale"):
        for annee in range(debut.year, fin.year + 1):
            jour = _occurrence_anniversaire(collegue.date_naissance, annee)
            if debut <= jour <= fin:
                occurrences.append({
                    "type": "ANNIVERSAIRE",
                    "titre": f"Anniversaire de {collegue.nom_complet}",
                    "date": jour,
                    "utilisateur_id": collegue.pk,
                    "filiale_id": collegue.filiale_id,
                })

    return sorted(occurrences, key=lambda o: (o["date"], o["titre"]))


def anniversaires_du_jour(jour=None):
    """
    Anniversaires du jour, tous périmètres confondus — destiné à la tâche
    de notification, qui n'agit pour aucun utilisateur en particulier.
    """
    jour = jour or date.today()

    return [
        collegue
        for collegue in User.objects.filter(
            is_active=True, date_naissance__isnull=False,
        ).select_related("filiale")
        if _occurrence_anniversaire(collegue.date_naissance, jour.year) == jour
    ]


def notifier_anniversaires(jour=None, dans_jours=0):
    """
    Prévient les collègues d'une même filiale d'un anniversaire.

    `dans_jours=1` annonce celui de demain — le rappel de veille, qui
    laisse le temps de s'organiser ; `dans_jours=0` annonce celui du jour.

    La personne concernée n'est jamais notifiée de son propre anniversaire.

    Idempotente au sens d'ACKS_LATE : ne modifie aucune donnée. Relancée,
    elle renotifie — jamais d'incohérence.
    """
    from datetime import timedelta

    from applications.notifications.services import envoyer_notification

    jour = jour or date.today()
    cible = jour + timedelta(days=dans_jours)

    if dans_jours == 0:
        titre = "Anniversaire aujourd'hui"
        formule = "fête son anniversaire aujourd'hui."
    else:
        titre = "Anniversaire demain"
        formule = f"fête son anniversaire le {cible:%d/%m}."

    envoyees = 0

    for celebre in anniversaires_du_jour(cible):
        if celebre.filiale_id is None:
            continue

        collegues = User.objects.filter(
            is_active=True, filiale_id=celebre.filiale_id,
        ).exclude(pk=celebre.pk)

        for collegue in collegues:
            envoyer_notification(
                collegue, titre,
                f"{celebre.nom_complet} {formule}",
                "INFO",
            )
            envoyees += 1

    return envoyees


def notifier_anniversaires_du_jour(jour=None):
    """Anniversaires du jour même. Conservée : la tâche existante l'appelle."""
    return notifier_anniversaires(jour, dans_jours=0)
