from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import LectureSeulePourTous
from applications.journalisation.services import enregistrer_action
from .models import Salle
from .serializers import SalleSerializer


class SalleViewSet(viewsets.ModelViewSet):
    """
    Salles de réunion. Lecture pour tous (un employé réserve partout — RG-03),
    écriture pour admin (toute filiale) et secrétaire (sa filiale — EF-11).
    """

    serializer_class = SalleSerializer
    permission_classes = [LectureSeulePourTous]
    filterset_fields = ("filiale", "active", "capacite")
    search_fields = ("nom", "filiale__nom")
    ordering_fields = ("nom", "capacite")

    def get_queryset(self):
        qs = Salle.objects.select_related("filiale").all()
        # Par défaut on n'expose que les salles actives en lecture simple
        if self.action == "list" and self.request.query_params.get("toutes") != "1":
            qs = qs.filter(active=True)
        return qs

    def perform_create(self, serializer):
        salle = serializer.save()
        enregistrer_action(self.request.user, "SALLE_CREEE", salle.nom, objet=salle)

    def perform_destroy(self, instance):
        enregistrer_action(self.request.user, "SALLE_SUPPRIMEE", instance.nom, objet=instance)
        instance.delete()

    @action(detail=False, methods=["get"])
    def equipements(self, request):
        """Liste des équipements possibles (pour les cases à cocher du front)."""
        return Response(
            [{"code": c, "libelle": l} for c, l in Salle.Equipement.choices]
        )
