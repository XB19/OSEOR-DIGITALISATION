from rest_framework import viewsets

from config.permissions import LectureSeulePourTous
from .models import Filiale
from .serializers import FilialeSerializer


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
