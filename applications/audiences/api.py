from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from applications.notifications.services import envoyer_notification
from applications.journalisation.services import enregistrer_action
from applications.reservations.models import Reservation
from .models import Audience, EchangeAudience, Delegation
from .serializers import (
    AudienceSerializer,
    EchangeAudienceSerializer,
    DelegationSerializer,
)


class AudienceViewSet(viewsets.ModelViewSet):
    serializer_class = AudienceSerializer
    filterset_fields = ("statut", "dg", "secretaire")
    search_fields = ("nom", "prenom", "objet_visite")
    ordering_fields = ("date_creation", "date_souhaitee")

    def get_queryset(self):
        qs = (
            Audience.objects
            .select_related("dg", "secretaire", "salle")
            .prefetch_related("echanges", "delegations")
        )
        u = self.request.user
        if u.role == "ADMINISTRATEUR":
            return qs
        if u.role == "DIRECTEUR":
            return qs.filter(dg=u)
        if u.role == "SECRETAIRE":
            return qs.filter(secretaire=u)
        # employé / délégué : audiences où il est délégué
        return qs.filter(delegations__delegue=u).distinct()

    def perform_create(self, serializer):
        serializer.save(secretaire=self.request.user, statut=Audience.Statut.SAISIE)

    # ---------------- Navette secrétaire -> DG (EF-13) ----------------
    @action(detail=True, methods=["post"])
    def envoyer_dg(self, request, pk=None):
        audience = self.get_object()
        audience.statut = Audience.Statut.ENVOYEE_DG
        audience.save(update_fields=["statut"])
        envoyer_notification(
            audience.dg,
            "Nouvelle demande d'audience",
            f"Audience de {audience.nom_complet} — {audience.objet_visite[:80]}",
            "INFO",
        )
        return Response(AudienceSerializer(audience).data)

    # ---------------- DG renvoie pour complément (EF-13) -------------
    @action(detail=True, methods=["post"])
    def renvoyer_secretaire(self, request, pk=None):
        audience = self.get_object()
        commentaire = request.data.get("commentaire", "")
        EchangeAudience.objects.create(
            audience=audience, auteur=request.user, commentaire=commentaire
        )
        audience.statut = Audience.Statut.RENVOYEE_SECRETAIRE
        audience.save(update_fields=["statut"])
        envoyer_notification(
            audience.secretaire,
            "Audience renvoyée pour complément",
            commentaire or "Le DG demande des précisions.",
            "WARNING",
        )
        return Response(AudienceSerializer(audience).data)

    # ---------------- Commentaire libre (navette) -------------------
    @action(detail=True, methods=["post"])
    def commenter(self, request, pk=None):
        audience = self.get_object()
        echange = EchangeAudience.objects.create(
            audience=audience,
            auteur=request.user,
            commentaire=request.data.get("commentaire", ""),
        )
        return Response(EchangeAudienceSerializer(echange).data, status=201)

    # ---------------- DG valide (EF-13) + réservation liée (RG-10) --
    @action(detail=True, methods=["post"])
    def valider_dg(self, request, pk=None):
        audience = self.get_object()
        if request.user.role != "DIRECTEUR":
            return Response(
                {"detail": "Seul le DG destinataire peut valider."},
                status=status.HTTP_403_FORBIDDEN,
            )
        audience.statut = Audience.Statut.VALIDEE_DG
        audience.save(update_fields=["statut"])

        # RG-10 : génère une demande de réservation si salle + créneau renseignés.
        if (
            audience.salle_id
            and audience.date_souhaitee
            and audience.heure_debut
            and audience.heure_fin
            and not audience.reservation_id
        ):
            reservation = Reservation(
                demandeur=audience.secretaire,
                nom_reservant=audience.nom_complet,
                salle=audience.salle,
                date_reunion=audience.date_souhaitee,
                heure_debut=audience.heure_debut,
                heure_fin=audience.heure_fin,
                precisions=f"Audience — {audience.objet_visite}",
                statut=Reservation.Statut.EN_ATTENTE,
            )
            try:
                reservation.save()
                audience.reservation = reservation
                audience.save(update_fields=["reservation"])
            except Exception as e:  # conflit de créneau
                return Response(
                    {"detail": "Audience validée, mais le créneau de salle est en conflit.",
                     "erreur": str(e)},
                    status=status.HTTP_409_CONFLICT,
                )

        envoyer_notification(
            audience.secretaire,
            "Audience validée par le DG",
            f"L'audience de {audience.nom_complet} est validée. Confirmez le rendez-vous.",
            "SUCCESS",
        )
        enregistrer_action(
            request.user, "AUDIENCE_VALIDEE_DG",
            f"Audience de {audience.nom_complet}", objet=audience,
        )
        return Response(AudienceSerializer(audience).data)

    # ---------------- Annulation (secrétaire / DG / admin) ----------
    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        """
        Annule une audience — par exemple quand le DG l'a renvoyée avec un
        commentaire du type « je ne veux pas de cette réunion ».
        Autorisé : la secrétaire qui a saisi la fiche, le DG destinataire,
        ou un administrateur.
        """
        audience = self.get_object()
        u = request.user
        autorise = (
            u.role == "ADMINISTRATEUR"
            or audience.secretaire_id == u.id
            or audience.dg_id == u.id
        )
        if not autorise:
            return Response(
                {"detail": "Vous ne pouvez pas annuler cette audience."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if audience.statut in (Audience.Statut.ANNULEE, Audience.Statut.TERMINEE):
            return Response(
                {"detail": "Cette audience est déjà annulée ou terminée."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        motif = request.data.get("motif", "")
        audience.statut = Audience.Statut.ANNULEE
        audience.save(update_fields=["statut"])

        # Trace dans la navette
        if motif:
            EchangeAudience.objects.create(
                audience=audience, auteur=u,
                commentaire=f"Audience annulée — {motif}",
            )

        # Annule aussi la réservation de salle liée (RG-10)
        if audience.reservation_id and audience.reservation.statut in Reservation.STATUTS_ACTIFS:
            reservation = audience.reservation
            reservation.statut = Reservation.Statut.ANNULEE
            reservation.annule_par = u
            reservation.motif_annulation = motif or "Audience annulée"
            reservation.save()

        # Notifie l'autre partie
        destinataire = audience.dg if audience.secretaire_id == u.id else audience.secretaire
        envoyer_notification(
            destinataire,
            "Audience annulée",
            f"L'audience de {audience.nom_complet} a été annulée."
            + (f" Motif : {motif}" if motif else ""),
            "WARNING",
        )
        enregistrer_action(
            u, "AUDIENCE_ANNULEE",
            f"Audience de {audience.nom_complet}", objet=audience, motif=motif,
        )
        return Response(AudienceSerializer(audience).data)

    # ---------------- Délégation (EF-14) ----------------------------
    @action(detail=True, methods=["post"])
    def deleguer(self, request, pk=None):
        audience = self.get_object()
        if request.user.role != "DIRECTEUR":
            return Response(
                {"detail": "Seul le DG peut déléguer."},
                status=status.HTTP_403_FORBIDDEN,
            )
        delegues_ids = request.data.get("delegues", [])
        commentaire = request.data.get("commentaire", "")
        if not isinstance(delegues_ids, list) or not delegues_ids:
            return Response(
                {"detail": "Fournir une liste 'delegues' d'identifiants utilisateurs."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        creees = []
        for uid in delegues_ids:
            delegation, cree = Delegation.objects.get_or_create(
                audience=audience, delegue_id=uid,
                defaults={"commentaire": commentaire},
            )
            if cree:
                creees.append(delegation)
                envoyer_notification(
                    delegation.delegue,
                    "Délégation d'audience",
                    commentaire or f"Vous êtes délégué pour l'audience de {audience.nom_complet}.",
                    "INFO",
                )
        if creees:
            enregistrer_action(
                request.user, "AUDIENCE_DELEGUEE",
                f"Audience de {audience.nom_complet}", objet=audience,
                delegues=[d.delegue_id for d in creees],
            )
        return Response(DelegationSerializer(creees, many=True).data, status=201)

    # ---------------- Confirmation finale (EF-17) -------------------
    @action(detail=True, methods=["post"])
    def confirmer(self, request, pk=None):
        audience = self.get_object()
        audience.statut = Audience.Statut.CONFIRMEE
        audience.date_confirmation = timezone.now()
        audience.save(update_fields=["statut", "date_confirmation"])
        # notifie DG + délégués
        envoyer_notification(
            audience.dg,
            "Audience confirmée",
            f"L'audience de {audience.nom_complet} est confirmée.",
            "SUCCESS",
        )
        for d in audience.delegations.all():
            envoyer_notification(
                d.delegue,
                "Audience confirmée",
                f"L'audience de {audience.nom_complet} est confirmée.",
                "SUCCESS",
            )
        enregistrer_action(
            request.user, "AUDIENCE_CONFIRMEE",
            f"Audience de {audience.nom_complet}", objet=audience,
        )
        return Response(AudienceSerializer(audience).data)


class DelegationViewSet(viewsets.ModelViewSet):
    serializer_class = DelegationSerializer
    filterset_fields = ("statut", "delegue", "audience")

    def get_queryset(self):
        qs = Delegation.objects.select_related("audience", "delegue")
        u = self.request.user
        if u.role in ("ADMINISTRATEUR", "DIRECTEUR"):
            return qs
        return qs.filter(delegue=u)

    @action(detail=True, methods=["post"])
    def prendre_en_compte(self, request, pk=None):
        """Le délégué accuse réception (il ne peut pas refuser — RG-11)."""
        delegation = self.get_object()
        if delegation.delegue_id != request.user.id:
            return Response(
                {"detail": "Seul le délégué concerné peut prendre en compte."},
                status=status.HTTP_403_FORBIDDEN,
            )
        delegation.statut = Delegation.Statut.PRISE_EN_COMPTE
        delegation.date_prise_en_compte = timezone.now()
        delegation.save(update_fields=["statut", "date_prise_en_compte"])
        # le DG est notifié de l'accusé de réception (EF-15)
        envoyer_notification(
            delegation.audience.dg,
            "Délégation prise en compte",
            f"{request.user.nom_complet} a pris connaissance de la délégation "
            f"pour l'audience de {delegation.audience.nom_complet}.",
            "SUCCESS",
        )
        return Response(DelegationSerializer(delegation).data)
