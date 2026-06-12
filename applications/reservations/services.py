from django.contrib.auth import get_user_model

from .models import Reservation
from applications.notifications.services import envoyer_notification

User = get_user_model()

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

    admins = User.objects.filter(
        filiale=salle.filiale,
        role="ADMIN_PRINCIPAL"
    )

    for admin in admins:
        envoyer_notification(
            admin,
            "Nouvelle réservation",
            f"Salle {salle.nom} le {date_reunion}",
            "INFO"
        )

    return reservation

def valider_reservation(reservation, admin):
    """
    Confirme une réservation + notifie le demandeur.
    """

    reservation.statut = Reservation.Statut.CONFIRMEE
    reservation.valide_par = admin
    reservation.save()

    envoyer_notification(
        reservation.demandeur,
        "Réservation confirmée",
        f"La salle {reservation.salle.nom} a été confirmée.",
        "SUCCESS"
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
        "ERROR"
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
        "WARNING"
    )

    return reservation