from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Reservation, SerieRecurrence
from .serializers import ReservationSerializer, SerieRecurrenceSerializer
from .services import (
    valider_reservation,
    refuser_reservation,
    annuler_reservation,
    generer_occurrences_serie,
)
from applications.journalisation.services import enregistrer_action
from applications.notifications.services import envoyer_notification


def _chevauche(salle_id, date_reunion, heure_debut, heure_fin, exclure_id=None):
    """Retourne les réservations actives en conflit avec le créneau donné."""
    qs = Reservation.objects.filter(
        salle_id=salle_id,
        date_reunion=date_reunion,
        statut__in=Reservation.STATUTS_ACTIFS,
        heure_debut__lt=heure_fin,
        heure_fin__gt=heure_debut,
    )
    if exclure_id:
        qs = qs.exclude(pk=exclure_id)
    return qs


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    filterset_fields = ("salle", "date_reunion", "statut", "demandeur", "salle__filiale")
    search_fields = ("nom_reservant", "salle__nom")
    ordering_fields = ("date_reunion", "heure_debut")

    def get_queryset(self):
        qs = (
            Reservation.objects
            .select_related("salle", "salle__filiale", "demandeur", "serie")
            .prefetch_related("participants")
        )
        params = self.request.query_params
        if params.get("mes") == "1":
            qs = qs.filter(demandeur=self.request.user)
        # bornes de dates pour le calendrier
        if params.get("date_min"):
            qs = qs.filter(date_reunion__gte=params["date_min"])
        if params.get("date_max"):
            qs = qs.filter(date_reunion__lte=params["date_max"])
        return qs

    def perform_create(self, serializer):
        reservation = serializer.save()
        enregistrer_action(
            self.request.user, "RESERVATION_CREEE",
            f"{reservation.nom_reservant} — {reservation.salle.nom} le {reservation.date_reunion}",
            objet=reservation,
        )

    def update(self, request, *args, **kwargs):
        """
        Modification (EF-09) : autorisée au secrétariat gestionnaire / admin,
        ou au demandeur jusqu'à 1h avant le début (RG-07).

        Règle post-validation :
        - Gestionnaire (admin/secrétaire) : peut modifier directement, statut conservé.
        - Demandeur : si la réservation était VALIDÉE, elle repasse EN_ATTENTE
          pour une nouvelle validation (les changements d'horaire doivent être reconfirmés).
        """
        reservation = self.get_object()
        u = request.user
        gestionnaire = (
            u.role == "ADMINISTRATEUR"
            or (u.role == "SECRETAIRE" and u.filiale_id == reservation.salle.filiale_id)
        )
        # Secrétaire/Admin propriétaire de la réservation : peut modifier à tout moment
        proprio_sans_restriction = (
            reservation.demandeur_id == u.id
            and u.role in ("SECRETAIRE", "ADMINISTRATEUR")
        )

        if not gestionnaire:
            if reservation.demandeur_id != u.id:
                return Response(
                    {"detail": "Vous ne pouvez pas modifier cette réservation."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if reservation.statut not in Reservation.STATUTS_ACTIFS:
                return Response(
                    {"detail": "Seule une demande en attente ou validée peut être modifiée."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not proprio_sans_restriction:
                debut = timezone.make_aware(
                    datetime.combine(reservation.date_reunion, reservation.heure_debut)
                )
                if timezone.now() > debut - timedelta(hours=1):
                    return Response(
                        {"detail": "Modification impossible à moins d'1h du début. "
                                   "Contactez le secrétariat."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        statut_avant = reservation.statut
        avant = {
            "date": reservation.date_reunion,
            "debut": reservation.heure_debut,
            "fin": reservation.heure_fin,
            "salle": reservation.salle.nom,
        }
        reponse = super().update(request, *args, **kwargs)

        # Gestionnaire modifie la réservation de quelqu'un d'autre →
        # le demandeur est prévenu du changement (ancien → nouveau + motif).
        if (
            reponse.status_code == 200
            and gestionnaire
            and reservation.demandeur_id != u.id
        ):
            reservation.refresh_from_db()
            changements = []
            if (avant["debut"] != reservation.heure_debut
                    or avant["fin"] != reservation.heure_fin):
                changements.append(
                    f"horaire {reservation.heure_debut:%H:%M}–{reservation.heure_fin:%H:%M} "
                    f"au lieu de {avant['debut']:%H:%M}–{avant['fin']:%H:%M}"
                )
            if avant["date"] != reservation.date_reunion:
                changements.append(
                    f"date {reservation.date_reunion} au lieu de {avant['date']}"
                )
            if avant["salle"] != reservation.salle.nom:
                changements.append(
                    f"salle {reservation.salle.nom} au lieu de {avant['salle']}"
                )
            if changements:
                motif_modif = request.data.get("motif_modification", "")
                message = (
                    f"Votre réservation du {reservation.date_reunion} "
                    f"a été modifiée par le secrétariat : {' ; '.join(changements)}."
                )
                if motif_modif:
                    message += f" Motif : {motif_modif}"
                envoyer_notification(
                    reservation.demandeur, "Réservation modifiée", message, "WARNING",
                )
                enregistrer_action(
                    u, "RESERVATION_MODIFIEE",
                    f"{reservation.nom_reservant} — {reservation.salle.nom} "
                    f"({' ; '.join(changements)})",
                    objet=reservation, motif=motif_modif,
                )

        # Si le demandeur modifie une réservation déjà validée → repasse EN_ATTENTE
        if reponse.status_code == 200 and not gestionnaire and statut_avant == Reservation.Statut.VALIDEE:
            reservation.refresh_from_db()
            reservation.statut = Reservation.Statut.EN_ATTENTE
            reservation.save(update_fields=["statut"])
            reponse.data["statut"] = Reservation.Statut.EN_ATTENTE
            reponse.data["statut_libelle"] = "En attente"
            enregistrer_action(
                u, "RESERVATION_MODIFIEE",
                f"{reservation.nom_reservant} — {reservation.salle.nom} le {reservation.date_reunion} "
                f"(repassée EN_ATTENTE après modification par le demandeur)",
                objet=reservation,
            )

        return reponse

    # ------------------------------------------------------------------
    # Contrôle de disponibilité avant soumission (EF-05 / RG-01)
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get"])
    def verifier_disponibilite(self, request):
        p = request.query_params
        requis = ("salle", "date_reunion", "heure_debut", "heure_fin")
        if not all(p.get(k) for k in requis):
            return Response(
                {"detail": "Paramètres requis : salle, date_reunion, heure_debut, heure_fin."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        conflits = _chevauche(
            p["salle"], p["date_reunion"], p["heure_debut"], p["heure_fin"],
            exclure_id=p.get("exclure"),
        )
        return Response({
            "disponible": not conflits.exists(),
            "conflits": ReservationSerializer(conflits, many=True).data,
        })

    # ------------------------------------------------------------------
    # Validation par le secrétariat de la filiale propriétaire (EF-06 / RG-02)
    # ------------------------------------------------------------------
    def _peut_valider(self, reservation):
        u = self.request.user
        if u.role == "ADMINISTRATEUR":
            return True
        return u.role == "SECRETAIRE" and u.filiale_id == reservation.salle.filiale_id

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        reservation = self.get_object()
        if not self._peut_valider(reservation):
            return Response(
                {"detail": "Seul le secrétariat de la filiale propriétaire peut valider."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if reservation.statut != Reservation.Statut.EN_ATTENTE:
            return Response(
                {"detail": "Seule une demande en attente peut être validée."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        valider_reservation(reservation, request.user)
        enregistrer_action(
            request.user, "RESERVATION_VALIDEE",
            f"{reservation.nom_reservant} — {reservation.salle.nom} le {reservation.date_reunion}",
            objet=reservation,
        )
        return Response(ReservationSerializer(reservation).data)

    @action(detail=True, methods=["post"])
    def refuser(self, request, pk=None):
        reservation = self.get_object()
        if not self._peut_valider(reservation):
            return Response(
                {"detail": "Action réservée au secrétariat de la filiale propriétaire."},
                status=status.HTTP_403_FORBIDDEN,
            )
        motif = request.data.get("motif", "")
        refuser_reservation(reservation, request.user, motif)
        enregistrer_action(
            request.user, "RESERVATION_REFUSEE",
            f"{reservation.nom_reservant} — {reservation.salle.nom}",
            objet=reservation, motif=motif,
        )
        return Response(ReservationSerializer(reservation).data)

    # ------------------------------------------------------------------
    # Annulation : par le demandeur (>1h avant — RG-07) ou le secrétariat
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        reservation = self.get_object()
        u = request.user
        motif = request.data.get("motif", "")

        est_gestionnaire = self._peut_valider(reservation)
        est_demandeur = reservation.demandeur_id == u.id

        if not (est_gestionnaire or est_demandeur):
            return Response(
                {"detail": "Vous ne pouvez pas annuler cette réservation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # RG-07 : le demandeur ne peut annuler que jusqu'à 1h avant le début.
        # Exception : secrétaire/admin propriétaire → peut annuler à tout moment.
        proprio_sans_restriction = (
            est_demandeur and u.role in ("SECRETAIRE", "ADMINISTRATEUR")
        )
        if est_demandeur and not est_gestionnaire and not proprio_sans_restriction:
            debut = timezone.make_aware(
                datetime.combine(reservation.date_reunion, reservation.heure_debut)
            )
            if timezone.now() > debut - timedelta(hours=1):
                return Response(
                    {"detail": "Annulation impossible à moins d'1h du début. "
                               "Contactez le secrétariat."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        annuler_reservation(reservation, u, motif)
        enregistrer_action(
            u, "RESERVATION_ANNULEE",
            f"{reservation.nom_reservant} — {reservation.salle.nom} le {reservation.date_reunion}",
            objet=reservation, motif=motif,
        )
        return Response(ReservationSerializer(reservation).data)

    # ------------------------------------------------------------------
    # Déplacement / arbitrage prioritaire par le secrétariat (EF-10)
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"])
    def deplacer(self, request, pk=None):
        reservation = self.get_object()
        if not self._peut_valider(reservation):
            return Response(
                {"detail": "Action réservée au secrétariat de la filiale propriétaire."},
                status=status.HTTP_403_FORBIDDEN,
            )
        motif = request.data.get("motif", "Arbitrage du secrétariat")
        reservation.statut = Reservation.Statut.DEPLACEE
        reservation.annule_par = request.user
        reservation.motif_annulation = motif
        reservation.save()
        # Message explicite au demandeur : créneau libéré, il doit reprogrammer.
        envoyer_notification(
            reservation.demandeur,
            "Réservation déplacée",
            f"Votre réservation du {reservation.date_reunion} en salle "
            f"{reservation.salle.nom} ({reservation.heure_debut:%H:%M}–"
            f"{reservation.heure_fin:%H:%M}) a été déplacée : le créneau a été "
            f"libéré par le secrétariat. Motif : {motif}. "
            f"Merci de reprogrammer sur un autre créneau.",
            "WARNING",
        )
        enregistrer_action(
            request.user, "RESERVATION_DEPLACEE",
            f"{reservation.nom_reservant} — {reservation.salle.nom}",
            objet=reservation, motif=motif,
        )
        return Response(ReservationSerializer(reservation).data)


class SerieRecurrenceViewSet(viewsets.ModelViewSet):
    """Séries récurrentes (EF-08). La création génère les occurrences."""

    queryset = SerieRecurrence.objects.select_related("salle").all()
    serializer_class = SerieRecurrenceSerializer
    filterset_fields = ("salle", "demandeur", "frequence")

    def perform_create(self, serializer):
        serie = serializer.save(demandeur=self.request.user)
        creees, conflits = generer_occurrences_serie(serie)
        self._resultat = {
            "occurrences_creees": len(creees),
            "occurrences_en_conflit": [str(d) for d in conflits],
        }

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if hasattr(self, "_resultat"):
            response.data["recurrence"] = self._resultat
        return response
