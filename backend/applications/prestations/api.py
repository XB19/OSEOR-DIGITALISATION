from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from applications.journalisation.services import enregistrer_action

from .models import JalonPrestation, Prestation
from .serializers import (
    JalonPrestationSerializer, PrestationEcritureSerializer,
    PrestationSerializer,
)
from . import services


class PrestationViewSet(viewsets.ModelViewSet):
    """
    Prestations de services, suivies par le service qui les réalise.

    Consultation selon le périmètre du service ; pilotage réservé au
    responsable de la prestation, au chef du service réalisateur et à la
    direction.
    """

    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("statut", "service", "filiale", "responsable")
    search_fields = ("reference", "intitule", "client")
    ordering_fields = ("date_debut", "date_fin_prevue", "montant")

    def get_queryset(self):
        return services.prestations_visibles(self.request.user)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PrestationEcritureSerializer
        return PrestationSerializer

    def _refus(self):
        return Response(
            {"detail": "Seuls le responsable, le chef du service réalisateur "
                       "et la direction peuvent modifier cette prestation."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def perform_create(self, serializer):
        filiale = serializer.validated_data["filiale"]
        prestation = serializer.save(
            reference=services.generer_reference(filiale))
        enregistrer_action(
            self.request.user, "PRESTATION_CREEE",
            f"{prestation.reference} — {prestation.intitule}", objet=prestation)

    def update(self, request, *args, **kwargs):
        if not services.peut_modifier(self.get_object(), request.user):
            return self._refus()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        prestation = self.get_object()
        if not services.peut_modifier(prestation, request.user):
            return self._refus()
        enregistrer_action(
            request.user, "PRESTATION_SUPPRIMEE",
            prestation.reference, objet=prestation)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        """
        Marque la prestation terminée et enregistre sa date de fin réelle,
        pour que l'écart avec la date prévue reste mesurable.
        """
        prestation = self.get_object()

        if not services.peut_modifier(prestation, request.user):
            return self._refus()
        if prestation.est_close:
            return Response(
                {"detail": "Cette prestation est déjà close."}, status=400)

        prestation.statut = Prestation.Statut.TERMINEE
        prestation.date_fin_reelle = timezone.localdate()
        prestation.save(update_fields=["statut", "date_fin_reelle"])

        enregistrer_action(
            request.user, "PRESTATION_CLOTUREE",
            prestation.reference, objet=prestation)

        return Response(
            PrestationSerializer(prestation, context={"request": request}).data)

    @action(detail=False, methods=["get"])
    def tableau_de_bord(self, request):
        """Répartition par statut et prestations en retard, sur le périmètre."""
        prestations = self.get_queryset()

        par_statut = {}
        for prestation in prestations:
            par_statut[prestation.statut] = par_statut.get(prestation.statut, 0) + 1

        en_retard = [p for p in prestations if p.en_retard]

        return Response({
            "total": len(prestations),
            "par_statut": par_statut,
            "en_retard": PrestationSerializer(
                en_retard, many=True, context={"request": request}).data,
        })


class JalonPrestationViewSet(viewsets.ModelViewSet):
    """Jalons d'une prestation — l'avancement réel s'y lit."""

    serializer_class = JalonPrestationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("prestation",)
    ordering_fields = ("date_prevue",)

    def get_queryset(self):
        visibles = services.prestations_visibles(self.request.user)
        return JalonPrestation.objects.filter(
            prestation__in=visibles).select_related("prestation")

    def _verifier_pilotage(self, prestation):
        return services.peut_modifier(prestation, self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prestation = serializer.validated_data["prestation"]
        if not self._verifier_pilotage(prestation):
            return Response(
                {"detail": "Vous ne pilotez pas cette prestation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if not self._verifier_pilotage(self.get_object().prestation):
            return Response(
                {"detail": "Vous ne pilotez pas cette prestation."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def realiser(self, request, pk=None):
        """Pointe le jalon comme réalisé, à la date du jour."""
        jalon = self.get_object()

        if not self._verifier_pilotage(jalon.prestation):
            return Response(
                {"detail": "Vous ne pilotez pas cette prestation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if jalon.date_realisation is None:
            jalon.date_realisation = timezone.localdate()
            jalon.save(update_fields=["date_realisation"])

        return Response(self.get_serializer(jalon).data)
