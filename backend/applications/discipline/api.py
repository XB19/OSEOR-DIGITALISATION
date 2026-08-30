from django.contrib.auth import get_user_model
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import ProcedureDisciplinaire
from .serializers import (
    BaremeDisciplinaireSerializer, ClassementSerializer, ConsignationSerializer,
    ExplicationSerializer, FormalitesSerializer, OuvertureSerializer,
    PrononceSerializer, ProcedureSerializer, SanctionSerializer,
)
from . import services
from .services import ProcedureRefusee

User = get_user_model()


class ProcedureDisciplinaireViewSet(mixins.ListModelMixin,
                                    mixins.RetrieveModelMixin,
                                    viewsets.GenericViewSet):
    """
    Dossiers disciplinaires.

    Le périmètre de lecture est le plus étroit de l'application : chacun
    voit le sien, les RH et la direction voient ceux de leur ressort.

    Lecture seule en REST classique — le dossier n'est pas un formulaire
    éditable, c'est une procédure encadrée par l'article 58 dont chaque
    étape a sa propre action et ses propres garanties.
    """

    serializer_class = ProcedureSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("statut", "salarie", "qualification", "filiale")
    search_fields = ("reference", "faits")
    ordering_fields = ("date_ouverture", "date_preuve")

    def get_queryset(self):
        return services.procedures_visibles(self.request.user)

    def create(self, request, *args, **kwargs):
        """Ouvre un dossier."""
        entree = OuvertureSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        salarie = User.objects.filter(
            pk=entree.validated_data["salarie"]).first()
        if salarie is None:
            return Response({"detail": "Salarié introuvable."}, status=400)

        try:
            procedure = services.ouvrir(
                salarie,
                entree.validated_data["faits"],
                entree.validated_data["date_faits"],
                entree.validated_data["date_preuve"],
                request.user,
                entree.validated_data["qualification"],
                entree.validated_data.get("faute_lourde_invoquee", ""),
                entree.validated_data.get("mise_a_pied_conservatoire", False),
            )
        except ProcedureRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(
            ProcedureSerializer(procedure).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def demander_explications(self, request, pk=None):
        """Invite formellement le salarié à s'expliquer."""
        try:
            procedure = services.demander_explications(
                self.get_object(), request.user)
        except ProcedureRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(ProcedureSerializer(procedure).data)

    @action(detail=True, methods=["post"],
            parser_classes=[MultiPartParser, FormParser])
    def expliquer(self, request, pk=None):
        """
        Consigne les explications du salarié — ou son refus, qui vaut
        garantie d'avoir été entendu.
        """
        entree = ConsignationSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            explication = services.consigner_explications(
                self.get_object(), request.user,
                entree.validated_data["mode"],
                entree.validated_data.get("contenu", ""),
                entree.validated_data.get("delegue_present", False),
                entree.validated_data.get("piece_jointe"),
            )
        except ProcedureRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(
            ExplicationSerializer(explication).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def prononcer(self, request, pk=None):
        """Prononce la sanction, sous les garanties de l'article 58."""
        entree = PrononceSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            sanction = services.prononcer(
                self.get_object(), request.user,
                entree.validated_data["type_sanction"],
                entree.validated_data["motif"],
                entree.validated_data.get("duree_jours"),
                entree.validated_data.get("date_prononce"),
            )
        except ProcedureRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(
            SanctionSerializer(sanction).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def formalites(self, request, pk=None):
        """
        Signification au salarié et ampliation à l'Inspection du Travail,
        toutes deux imposées par l'article 58.
        """
        procedure = self.get_object()
        sanction = getattr(procedure, "sanction", None)

        if sanction is None:
            return Response(
                {"detail": "Aucune sanction n'a été prononcée."}, status=400)

        entree = FormalitesSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            sanction = services.enregistrer_formalites(
                sanction, request.user,
                entree.validated_data.get("date_notification"),
                entree.validated_data.get("date_inspection_travail"),
            )
        except ProcedureRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(SanctionSerializer(sanction).data)

    @action(detail=True, methods=["post"])
    def classer(self, request, pk=None):
        """Classe le dossier sans suite ; il reste consultable."""
        entree = ClassementSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            procedure = services.classer(
                self.get_object(), request.user,
                entree.validated_data["motif"])
        except ProcedureRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(ProcedureSerializer(procedure).data)

    @action(detail=False, methods=["get"])
    def bareme(self, request):
        """Barème de l'article 58 et énumération des fautes lourdes."""
        return Response(BaremeDisciplinaireSerializer.bareme())
