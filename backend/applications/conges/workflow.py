"""
Parcours d'une demande de congé : dépôt, validation, refus, annulation.

Qui valide se lit dans l'organigramme, via `Utilisateur.valideur_conge` :
le responsable hiérarchique direct, à défaut le chef de service, et si
personne n'est désigné, les RH prennent le relais. C'est la différence
avec la chaîne de visas des documents administratifs, qui s'adresse à un
RÔLE : un congé se valide par **mon** responsable, pas par n'importe quel
chef de service du groupe.
"""

from django.db import transaction
from django.utils import timezone

from applications.journalisation.services import enregistrer_action
from applications.notifications.services import envoyer_notification
from config.permissions import RH, est_direction

from . import services
from .calendrier import compter_jours_ouvres
from .convention import (
    ANCIENNETE_REQUISE_MOIS, exige_anciennete, jours_accordes, regle,
)
from .models import DemandeConge, TypeConge


class DemandeRefusee(Exception):
    """Règle métier violée : le motif est destiné à l'utilisateur."""


def valideurs_possibles(demande):
    """
    Qui peut trancher cette demande.

    Toujours la direction (elle arbitre tout) et les RH (filet de sécurité
    quand aucun responsable n'est renseigné), plus le valideur désigné par
    l'organigramme.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    identifiants = set(
        User.objects.filter(
            is_active=True, role__in=("ADMINISTRATEUR", "DIRECTEUR", RH),
        ).values_list("pk", flat=True)
    )

    valideur = demande.utilisateur.valideur_conge
    if valideur is not None:
        identifiants.add(valideur.pk)

    # Personne ne valide sa propre demande, quel que soit son rôle.
    identifiants.discard(demande.utilisateur_id)

    return identifiants


def peut_valider(demande, utilisateur):
    if demande.utilisateur_id == utilisateur.pk:
        return False
    if est_direction(utilisateur) or utilisateur.role == RH:
        return True
    return utilisateur.pk in valideurs_possibles(demande)


def _chevauchement(utilisateur, date_debut, date_fin, exclure=None):
    """Demandes en cours du salarié recoupant la période visée."""
    demandes = DemandeConge.objects.filter(
        utilisateur=utilisateur,
        statut__in=(DemandeConge.Statut.EN_ATTENTE, DemandeConge.Statut.VALIDEE),
        date_debut__lte=date_fin,
        date_fin__gte=date_debut,
    )
    if exclure is not None:
        demandes = demandes.exclude(pk=exclure.pk)
    return demandes


def _anciennete_mois(utilisateur, reference):
    """Mois de service révolus à la date de référence."""
    embauche = utilisateur.date_embauche
    if embauche is None:
        return 0

    mois = (reference.year - embauche.year) * 12 + (reference.month - embauche.month)
    if reference.day < embauche.day:
        mois -= 1
    return max(mois, 0)


def _verifier_permission(utilisateur, motif_permission, jours, date_debut):
    """
    Contrôles propres aux permissions exceptionnelles (article 45 CCIT).

    Le barème fixe un droit maximal par évènement ; la condition de six
    mois d'ancienneté vaut pour les permissions syndicales mais pas pour
    les évènements familiaux, que l'article dispense expressément.
    """
    regle_motif = regle(motif_permission)
    if regle_motif is None:
        raise DemandeRefusee(
            "Motif de permission inconnu au barème de l'article 45."
        )

    droit = jours_accordes(motif_permission)
    if jours > droit:
        raise DemandeRefusee(
            f"« {regle_motif['libelle']} » ouvre droit à {droit} jour(s) ; "
            f"{jours} jour(s) demandé(s)."
        )

    if exige_anciennete(motif_permission):
        anciennete = _anciennete_mois(utilisateur, date_debut)
        if anciennete < ANCIENNETE_REQUISE_MOIS:
            raise DemandeRefusee(
                f"Cette permission demande {ANCIENNETE_REQUISE_MOIS} mois "
                f"d'ancienneté ; vous en comptez {anciennete}."
            )


def deposer(utilisateur, type_conge, date_debut, date_fin, motif="",
            motif_permission="", date_evenement=None):
    """
    Dépose une demande de congé ou de permission après vérification des
    règles métier.

    Lève `DemandeRefusee` avec un message destiné à l'utilisateur.
    """
    if date_fin < date_debut:
        raise DemandeRefusee("La date de fin ne peut pas précéder la date de début.")

    jours = compter_jours_ouvres(date_debut, date_fin, utilisateur.filiale)
    if jours == 0:
        raise DemandeRefusee(
            "Cette période ne contient aucun jour ouvré : week-ends et jours "
            "fériés ne se posent pas en congé."
        )

    if _chevauchement(utilisateur, date_debut, date_fin).exists():
        raise DemandeRefusee(
            "Vous avez déjà une demande en cours sur cette période."
        )

    if type_conge == TypeConge.PERMISSION:
        if not motif_permission:
            raise DemandeRefusee(
                "Précisez l'évènement invoqué : le barème de l'article 45 "
                "fixe un nombre de jours par motif."
            )
        _verifier_permission(utilisateur, motif_permission, jours, date_debut)
    elif motif_permission:
        raise DemandeRefusee(
            "Un motif de permission ne se renseigne que sur une permission "
            "exceptionnelle."
        )

    demande = DemandeConge(
        utilisateur=utilisateur,
        type_conge=type_conge,
        date_debut=date_debut,
        date_fin=date_fin,
        jours_ouvres=jours,
        motif=motif,
        motif_permission=motif_permission,
        date_evenement=date_evenement,
    )

    if demande.decompte_le_solde:
        # Solde cumulatif : les jours non pris se reportent sans limite de
        # temps, une demande de janvier peut donc puiser dans des droits
        # acquis les années précédentes.
        disponible = services.solde_disponible(utilisateur)
        if jours > disponible:
            raise DemandeRefusee(
                f"Solde insuffisant : {jours} jour(s) demandé(s) pour "
                f"{disponible} jour(s) disponible(s)."
            )

    with transaction.atomic():
        demande.save()
        enregistrer_action(
            utilisateur, "CONGE_DEMANDE",
            f"{date_debut:%d/%m/%Y} au {date_fin:%d/%m/%Y} ({jours} j)",
            objet=demande,
        )

    _notifier_valideurs(demande)
    return demande


def _notifier_valideurs(demande):
    from django.contrib.auth import get_user_model

    User = get_user_model()

    valideur = demande.utilisateur.valideur_conge
    destinataires = (
        [valideur] if valideur is not None
        else list(User.objects.filter(is_active=True, role=RH))
    )

    for destinataire in destinataires:
        envoyer_notification(
            destinataire,
            "Demande de congé à valider",
            f"{demande.utilisateur.nom_complet} — "
            f"{demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y} "
            f"({demande.jours_ouvres} j)",
            "INFO",
            objet=demande,
        )


def decider(demande, valideur, approuvee, motif=""):
    """
    Valide ou refuse une demande, et débite le solde le cas échéant.

    Le débit et le changement de statut sont dans la même transaction :
    une demande validée dont le solde n'aurait pas bougé donnerait des
    jours gratuits.
    """
    if demande.statut != DemandeConge.Statut.EN_ATTENTE:
        raise DemandeRefusee("Cette demande a déjà été traitée.")

    if not peut_valider(demande, valideur):
        raise DemandeRefusee("Vous n'êtes pas habilité à traiter cette demande.")

    with transaction.atomic():
        demande.statut = (
            DemandeConge.Statut.VALIDEE if approuvee
            else DemandeConge.Statut.REFUSEE
        )
        demande.valideur = valideur
        demande.date_decision = timezone.now()
        demande.motif_decision = motif
        demande.save()

        if approuvee:
            services.consommer(demande)

        enregistrer_action(
            valideur,
            "CONGE_VALIDE" if approuvee else "CONGE_REFUSE",
            f"{demande.utilisateur.nom_complet} — "
            f"{demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y}",
            objet=demande,
        )

    envoyer_notification(
        demande.utilisateur,
        "Congé validé" if approuvee else "Congé refusé",
        f"{demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y}"
        + (f" — {motif}" if motif else ""),
        "SUCCESS" if approuvee else "ERROR",
        objet=demande,
    )

    return demande


def annuler(demande, utilisateur, motif=""):
    """
    Annule une demande et restitue les jours déjà débités.

    Le salarié peut annuler la sienne ; la direction et les RH peuvent
    annuler celle d'un autre — un congé validé puis annulé doit rendre ses
    jours, sinon le salarié les perd sans les avoir pris.
    """
    if demande.statut in (DemandeConge.Statut.ANNULEE, DemandeConge.Statut.REFUSEE):
        raise DemandeRefusee("Cette demande n'est plus active.")

    autorise = (
        demande.utilisateur_id == utilisateur.pk
        or est_direction(utilisateur)
        or utilisateur.role == RH
    )
    if not autorise:
        raise DemandeRefusee("Vous ne pouvez pas annuler cette demande.")

    with transaction.atomic():
        demande.statut = DemandeConge.Statut.ANNULEE
        demande.motif_decision = motif
        demande.save()

        services.restituer(demande)

        enregistrer_action(
            utilisateur, "CONGE_ANNULE",
            f"{demande.utilisateur.nom_complet} — "
            f"{demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y}",
            objet=demande,
        )

    if demande.utilisateur_id != utilisateur.pk:
        envoyer_notification(
            demande.utilisateur,
            "Congé annulé",
            f"{demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y}"
            + (f" — {motif}" if motif else ""),
            "WARNING",
            objet=demande,
        )

    return demande
