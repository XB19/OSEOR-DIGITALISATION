from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Reservation
from applications.notifications.services import envoyer_notification

User = get_user_model()


def generer_occurrences_serie(serie):
    """
    Génère les occurrences (Reservation) d'une série récurrente (EF-08).

    Le contrôle de chevauchement (RG-01) s'applique à chaque occurrence :
    celles en conflit sont ignorées et retournées séparément pour
    arbitrage / information du demandeur.

    Retourne (occurrences_creees, occurrences_en_conflit).
    """
    creees = []
    conflits = []

    jours = set(serie.jours_semaine or [])
    pas = 1  # incrément en semaines pour les fréquences hebdomadaires
    if serie.frequence == serie.Frequence.BIHEBDOMADAIRE:
        pas = 2

    jour = serie.date_debut
    while jour <= serie.date_fin:
        retenu = False

        if serie.frequence == serie.Frequence.QUOTIDIENNE:
            retenu = jour.weekday() < 5  # lun-ven
        elif serie.frequence in (
            serie.Frequence.HEBDOMADAIRE,
            serie.Frequence.BIHEBDOMADAIRE,
        ):
            if jours:
                retenu = jour.weekday() in jours
            else:
                retenu = jour.weekday() == serie.date_debut.weekday()
            if retenu and pas == 2:
                # une semaine sur deux à partir de la date de début
                semaines = (jour - serie.date_debut).days // 7
                retenu = (semaines % 2 == 0)
        elif serie.frequence == serie.Frequence.MENSUELLE:
            retenu = jour.day == serie.date_debut.day

        if retenu:
            # Secrétaire/Admin → validation immédiate sans circuit d'approbation
            est_gestionnaire = serie.demandeur.role in ("SECRETAIRE", "ADMINISTRATEUR")
            statut_initial = (
                Reservation.Statut.VALIDEE if est_gestionnaire
                else Reservation.Statut.EN_ATTENTE
            )
            occurrence = Reservation(
                demandeur=serie.demandeur,
                nom_reservant=serie.nom_reservant,
                telephone=serie.telephone,
                motif=serie.motif,
                salle=serie.salle,
                serie=serie,
                date_reunion=jour,
                heure_debut=serie.heure_debut,
                heure_fin=serie.heure_fin,
                precisions=serie.precisions,
                statut=statut_initial,
            )
            try:
                occurrence.save()  # save() appelle full_clean() (contrôle chevauchement)
                creees.append(occurrence)
            except ValidationError:
                conflits.append(jour)

        jour += timedelta(days=1)

    return creees, conflits

def creer_reservation(
    demandeur,
    salle,
    nom_reservant,
    date_reunion,
    heure_debut,
    heure_fin,
    precisions=""
):
    """
    Crée une réservation + notifie les admins.
    """

    reservation = Reservation.objects.create(
        demandeur=demandeur,
        salle=salle,
        nom_reservant=nom_reservant,
        date_reunion=date_reunion,
        heure_debut=heure_debut,
        heure_fin=heure_fin,
        precisions=precisions
    )

    # RG-02 : la demande va au secrétariat qui gère la salle
    # (filiale propriétaire de la salle), pas à celui du demandeur.
    secretaires = User.objects.filter(
        filiale=salle.filiale,
        role=User.Role.SECRETAIRE
    )

    for secretaire in secretaires:
        envoyer_notification(
            secretaire,
            "Nouvelle demande de réservation",
            f"Salle {salle.nom} le {date_reunion}",
            "INFO",
            objet=reservation,
        )

    return reservation

def valider_reservation(reservation, secretaire):
    """
    Valide une réservation + notifie le demandeur.
    """
    from django.utils import timezone

    reservation.statut = Reservation.Statut.VALIDEE
    reservation.valide_par = secretaire
    reservation.date_validation = timezone.now()
    reservation.save()

    envoyer_notification(
        reservation.demandeur,
        "Réservation validée",
        f"La salle {reservation.salle.nom} a été validée.",
        "SUCCESS",
        objet=reservation,
    )

    return reservation

def refuser_reservation(reservation, admin, motif):
    """
    Refuse une réservation + notifie le demandeur.
    """

    reservation.statut = Reservation.Statut.REFUSEE
    reservation.valide_par = admin
    reservation.motif_refus = motif
    reservation.save()

    envoyer_notification(
        reservation.demandeur,
        "Réservation refusée",
        f"Motif : {motif}",
        "ERROR",
        objet=reservation,
    )

    return reservation

def annuler_reservation(reservation, utilisateur, motif):
    """
    Annule une réservation + notifie le demandeur.
    """

    reservation.statut = Reservation.Statut.ANNULEE
    reservation.annule_par = utilisateur
    reservation.motif_annulation = motif
    reservation.save()

    envoyer_notification(
        reservation.demandeur,
        "Réservation annulée",
        f"Motif : {motif}",
        "WARNING",
        objet=reservation,
    )

    return reservation