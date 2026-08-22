from rest_framework import viewsets

from config.permissions import LectureSeulePourTous
from .models import Filiale, Service
from .serializers import FilialeSerializer, ServiceSerializer


class FilialeViewSet(viewsets.ModelViewSet):
    """
    Filiales du groupe. Lecture pour tous (sert aux listes déroulantes),
    écriture réservée admin/secrétaire.
    """

    queryset = Filiale.objects.prefetch_related("parametres").all()
    serializer_class = FilialeSerializer
    permission_classes = [LectureSeulePourTous]
    filterset_fields = ("active",)
    search_fields = ("nom", "code")
    ordering_fields = ("nom",)


class ServiceViewSet(viewsets.ModelViewSet):
    """
    Services (départements) d'une filiale. Lecture pour tous — les listes
    déroulantes « service » en ont besoin — écriture réservée
    admin/secrétaire, comme les filiales.
    """

    serializer_class = ServiceSerializer
    permission_classes = [LectureSeulePourTous]
    filterset_fields = ("filiale", "actif")
    search_fields = ("nom", "code")
    ordering_fields = ("nom",)

    def get_queryset(self):
        return (
            Service.objects
            .select_related("filiale", "chef")
            .prefetch_related("membres")
            .all()
        )
