"""
Parcours d'une demande de congé : dépôt, validation, refus, annulation.

Le parcours de validation lui-même est décrit dans `circuits.py` et
exécuté par le socle commun (`applications.validation`) : un congé passe
par le responsable hiérarchique puis par la direction, une demande de
directeur par les RH puis par un pair, une permission par le seul
responsable.

Ce qui reste ici, c'est le métier propre aux congés : contrôle du solde,
des chevauchements, du barème conventionnel, et les écritures au registre.

Qui valide se lit dans l'organigramme, non dans les rôles : un congé se
valide par **mon** responsable, pas par n'importe quel chef de service du
groupe. C'est la différence de fond avec la chaîne de visas documentaire,
et le socle porte les deux modes de désignation.
"""

from django.db import transaction
from django.utils import timezone

from applications.journalisation.services import enregistrer_action
from applications.notifications.services import envoyer_notification
from config.permissions import RH, est_direction

from applications.validation import services as validation
from applications.validation.circuits import peut_agir, resoudre_acteurs
from applications.validation.services import ValidationRefusee

from . import services
from .calendrier import compter_jours_ouvres
from .circuits import circuit_pour
from .convention import (
    ANCIENNETE_REQUISE_MOIS, exige_anciennete, jours_accordes, regle,
)
from .models import DemandeConge, TypeConge


class DemandeRefusee(Exception):
    """Règle métier violée : le motif est destiné à l'utilisateur."""


def valideurs_possibles(demande):
    """
    Identifiants des personnes pouvant trancher la demande à son étape
    courante — acteurs de l'étape, plus les autorités qui peuvent valider
    directement.
    """
    circuit = circuit_pour(demande)
    etape = circuit.etape(demande.etape_validation)
    if etape is None:
        return set()

    identifiants = set(
        resoudre_acteurs(etape, demande.utilisateur, demande))

    # Les autorités en aval peuvent conclure sans attendre.
    for suivante in circuit.etapes[demande.etape_validation:]:
        if suivante.autorite:
            identifiants |= resoudre_acteurs(
                suivante, demande.utilisateur, demande)

    identifiants.discard(demande.utilisateur_id)
    return identifiants


def peut_valider(demande, utilisateur):
    """True si `utilisateur` peut trancher l'étape courante."""
    if demande.statut != DemandeConge.Statut.EN_ATTENTE:
        return False
    return peut_agir(
        circuit_pour(demande), demande.etape_validation,
        utilisateur, demande.utilisateur, demande,
    )


def etape_courante(demande):
    """Étape de validation en cours, ou None si le circuit est terminé."""
    return circuit_pour(demande).etape(demande.etape_validation)


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
    """Prévient les acteurs de l'étape courante du circuit."""
    circuit = circuit_pour(demande)
    etape = circuit.etape(demande.etape_validation)
    libelle = etape.libelle if etape else "Validation"

    return validation.notifier_etape(
        demande, circuit, demande.etape_validation, demande.utilisateur,
        "Demande de congé à valider",
        f"{demande.utilisateur.nom_complet} — "
        f"{demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y} "
        f"({demande.jours_ouvres} j) — {libelle}",
    )


def _informer_observateurs(demande, entete, type_notification="INFO"):
    """
    Tient RH et comptabilité au courant, sans jamais les solliciter.

    Ils reçoivent l'information complète : qui s'absente, quand, combien de
    jours, et qui a tranché.
    """
    valideur = demande.valideur.nom_complet if demande.valideur else "—"

    return validation.notifier_observateurs(
        demande, circuit_pour(demande), entete,
        f"{demande.utilisateur.nom_complet} — {demande.get_type_conge_display()} — "
        f"{demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y} "
        f"({demande.jours_ouvres} j) — décision : {valideur}",
        type_notification,
        exclure=(demande.utilisateur, demande.valideur),
    )


def decider(demande, valideur, approuvee, motif=""):
    """
    Tranche l'étape courante du circuit.

    Une validation ne clôt la demande que si le circuit est épuisé : le
    congé d'un salarié demande l'accord du responsable PUIS de la
    direction. Une autorité peut cependant conclure seule — la décision
    consigne alors les étapes qu'elle a sautées.

    Le débit du solde et le changement de statut sont dans la même
    transaction : une demande validée dont le solde n'aurait pas bougé
    donnerait des jours gratuits. La demande est relue sous verrou, sans
    quoi deux validations simultanées passeraient toutes deux le contrôle
    de statut et consommeraient le solde en double.
    """
    circuit = circuit_pour(demande)
    # L'appelant garde une référence sur SON instance : on travaille sur une
    # copie verrouillée, puis on la resynchronise avant de rendre la main.
    # Sans cela il observerait un objet périmé et croirait la décision sans
    # effet.
    demande_appelant = demande

    with transaction.atomic():
        demande = (
            DemandeConge.objects
            .select_for_update()
            .select_related("utilisateur", "valideur")
            .get(pk=demande.pk)
        )

        if demande.statut != DemandeConge.Statut.EN_ATTENTE:
            raise DemandeRefusee("Cette demande a déjà été traitée.")

        try:
            decision, etape_suivante = validation.enregistrer_decision(
                demande, circuit, demande.etape_validation, valideur,
                demande.utilisateur, approuvee, motif,
            )
        except ValidationRefusee as erreur:
            raise DemandeRefusee(str(erreur)) from erreur

        demande.etape_validation = etape_suivante
        demande.valideur = valideur
        demande.date_decision = timezone.now()
        demande.motif_decision = motif

        if not approuvee:
            demande.statut = DemandeConge.Statut.REFUSEE
        elif etape_suivante >= len(circuit):
            demande.statut = DemandeConge.Statut.VALIDEE

        demande.save()

        if demande.statut == DemandeConge.Statut.VALIDEE:
            services.consommer(demande)

        enregistrer_action(
            valideur,
            "CONGE_VALIDE" if approuvee else "CONGE_REFUSE",
            f"{demande.utilisateur.nom_complet} — "
            f"{demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y}"
            + (" (validation directe)" if decision.validation_directe else ""),
            objet=demande,
        )

    # Notifications hors transaction : une panne d'envoi ne doit pas
    # annuler une décision déjà prise.
    if demande.statut == DemandeConge.Statut.EN_ATTENTE:
        _notifier_valideurs(demande)
        demande_appelant.refresh_from_db()
        return demande_appelant

    envoyer_notification(
        demande.utilisateur,
        "Congé validé" if approuvee else "Congé refusé",
        f"{demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y}"
        + (f" — {motif}" if motif else ""),
        "SUCCESS" if approuvee else "ERROR",
        objet=demande,
    )

    _informer_observateurs(
        demande,
        "Congé validé" if approuvee else "Congé refusé",
        "INFO" if approuvee else "WARNING",
    )

    demande_appelant.refresh_from_db()
    return demande_appelant


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
