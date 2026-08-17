from rest_framework import viewsets, mixins

from config.permissions import EstAdministrateur
from .models import JournalAction
from .serializers import JournalActionSerializer


class JournalActionViewSet(mixins.ListModelMixin,
                           mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):
    """Consultation du journal d'audit — réservée à l'administrateur (EF-20)."""

    queryset = JournalAction.objects.select_related("acteur").all()
    serializer_class = JournalActionSerializer
    permission_classes = [EstAdministrateur]
    filterset_fields = ("action", "objet_type", "acteur")
    search_fields = ("action", "cible")
    ordering_fields = ("date_creation",)
