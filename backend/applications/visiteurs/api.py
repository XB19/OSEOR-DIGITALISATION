from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from config.permissions import (
    ADMINISTRATEUR, AGENT_SECURITE, DIRECTEUR, SECRETAIRE,
    EstUnDes, restreindre_a_la_filiale,
)

from .models import Visite
from .serializers import VisiteSerializer


class VisiteViewSet(mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    Registre des visiteurs de l'accueil : l'agent de sécurité (ou la
    secrétaire, en couverture mutuelle) enregistre une arrivée puis marque
    le départ quand le visiteur récupère sa pièce d'identité.
    """

    serializer_class = VisiteSerializer
    permission_classes = [EstUnDes(AGENT_SECURITE, SECRETAIRE, ADMINISTRATEUR, DIRECTEUR)]
    filterset_fields = ("heure_depart",)
    ordering_fields = ("heure_arrivee",)

    def get_queryset(self):
        queryset = restreindre_a_la_filiale(Visite.objects.all(), self.request.user)
        if self.request.query_params.get("present") in ("1", "true", "True"):
            queryset = queryset.filter(heure_depart__isnull=True)
        return queryset

    def perform_create(self, serializer):
        utilisateur = self.request.user
        if not utilisateur.filiale_id:
            raise ValidationError("Votre compte n'est rattaché à aucune filiale : impossible d'enregistrer une visite.")
        serializer.save(filiale=utilisateur.filiale, enregistre_par=utilisateur)

    @action(detail=True, methods=["post"])
    def marquer_depart(self, request, pk=None):
        visite = self.get_object()
        if visite.heure_depart is not None:
            raise ValidationError("Le départ de ce visiteur a déjà été enregistré.")
        visite.heure_depart = timezone.now()
        visite.save(update_fields=["heure_depart"])
        return Response(VisiteSerializer(visite).data)
