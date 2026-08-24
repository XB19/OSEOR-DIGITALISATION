from datetime import date

from rest_framework import mixins, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from config.permissions import RH, est_direction, restreindre_a_la_filiale

from .models import DemandeConge, JourFerie, MouvementConge
from .serializers import (
    AnnulationSerializer, BaremePermissionSerializer, DecisionSerializer,
    DemandeCongeSerializer, DepotDemandeSerializer, JourFerieSerializer,
    MouvementCongeSerializer,
)
from . import services, workflow
from .workflow import DemandeRefusee


class DemandeCongeViewSet(mixins.ListModelMixin,
                          mixins.RetrieveModelMixin,
                          viewsets.GenericViewSet):
    """
    Demandes de congé.

    Chacun voit les siennes ; la direction et les RH voient tout le
    groupe ; un responsable voit celles de ses subordonnés. Les
    modifications passent par les actions dédiées (`decider`, `annuler`) et
    jamais par un PUT : une demande n'est pas un formulaire éditable, c'est
    un parcours de décisions tracées.
    """

    serializer_class = DemandeCongeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("statut", "type_conge", "utilisateur")
    ordering_fields = ("date_debut", "date_creation")

    def get_queryset(self):
        utilisateur = self.request.user
        queryset = DemandeConge.objects.select_related(
            "utilisateur", "valideur", "utilisateur__filiale")

        if est_direction(utilisateur) or utilisateur.role == RH:
            return queryset

        subordonnes = utilisateur.subordonnes.values_list("pk", flat=True)
        return queryset.filter(
            utilisateur__in=[utilisateur.pk, *subordonnes])

    def create(self, request, *args, **kwargs):
        """Dépose une demande pour l'utilisateur connecté."""
        entree = DepotDemandeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            demande = workflow.deposer(
                request.user,
                entree.validated_data["type_conge"],
                entree.validated_data["date_debut"],
                entree.validated_data["date_fin"],
                entree.validated_data["motif"],
                motif_permission=entree.validated_data.get("motif_permission", ""),
                date_evenement=entree.validated_data.get("date_evenement"),
            )
        except DemandeRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(
            DemandeCongeSerializer(demande).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def decider(self, request, pk=None):
        """Valide ou refuse la demande."""
        entree = DecisionSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            demande = workflow.decider(
                self.get_object(), request.user,
                entree.validated_data["approuvee"],
                entree.validated_data["motif"],
            )
        except DemandeRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(DemandeCongeSerializer(demande).data)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        """Annule la demande et restitue les jours déjà débités."""
        entree = AnnulationSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            demande = workflow.annuler(
                self.get_object(), request.user, entree.validated_data["motif"])
        except DemandeRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(DemandeCongeSerializer(demande).data)

    @action(detail=False, methods=["get"])
    def bareme_permissions(self, request):
        """
        Barème des permissions exceptionnelles (article 45 de la CCIT) :
        motifs, jours accordés, justificatif attendu et condition
        d'ancienneté. Alimente la liste déroulante du formulaire.
        """
        return Response(BaremePermissionSerializer.bareme())

    @action(detail=True, methods=["post"],
            parser_classes=[MultiPartParser, FormParser])
    def justificatif(self, request, pk=None):
        """
        Dépose la pièce justifiant l'évènement — l'article 45 impose de la
        produire « au plus tard huit jours après que l'évènement ait eu
        lieu ».
        """
        demande = self.get_object()

        if not demande.est_permission:
            return Response(
                {"detail": "Seule une permission exceptionnelle demande un "
                           "justificatif."}, status=400)

        autorise = (
            demande.utilisateur_id == request.user.pk
            or est_direction(request.user)
            or request.user.role == RH
        )
        if not autorise:
            return Response(
                {"detail": "Vous ne pouvez pas déposer de pièce sur cette "
                           "demande."},
                status=status.HTTP_403_FORBIDDEN,
            )

        fichier = request.data.get("justificatif")
        if not fichier:
            return Response({"detail": "Aucun fichier transmis."}, status=400)

        demande.justificatif = fichier
        demande.save(update_fields=["justificatif"])

        return Response(DemandeCongeSerializer(demande).data)

    @action(detail=False, methods=["get"])
    def mon_solde(self, request):
        """
        Compteur de l'utilisateur connecté : acquis, pris, réservé,
        disponible. Paramètre `annee` facultatif.
        """
        try:
            annee = int(request.query_params.get("annee", date.today().year))
        except ValueError:
            return Response({"detail": "Année invalide."}, status=400)

        return Response(services.situation(request.user, annee))

    @action(detail=False, methods=["get"])
    def mon_registre(self, request):
        """
        Détail des mouvements de l'utilisateur : d'où vient chaque jour, et
        ce qui a été perdu au 31 décembre.
        """
        try:
            annee = int(request.query_params.get("annee", date.today().year))
        except ValueError:
            return Response({"detail": "Année invalide."}, status=400)

        mouvements = MouvementConge.objects.filter(
            utilisateur=request.user, annee=annee)

        return Response(MouvementCongeSerializer(mouvements, many=True).data)

    @action(detail=False, methods=["get"])
    def a_valider(self, request):
        """Demandes en attente que l'utilisateur peut trancher."""
        en_attente = self.get_queryset().filter(
            statut=DemandeConge.Statut.EN_ATTENTE,
        ).exclude(utilisateur=request.user)

        traitables = [
            demande for demande in en_attente
            if workflow.peut_valider(demande, request.user)
        ]

        return Response(DemandeCongeSerializer(traitables, many=True).data)


class JourFerieViewSet(viewsets.ModelViewSet):
    """
    Jours fériés. Lecture pour tous — le calendrier et le calcul des jours
    ouvrés en dépendent — écriture réservée aux RH et à l'administrateur,
    qui y saisissent les fêtes mobiles fixées par décret.
    """

    serializer_class = JourFerieSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("filiale",)
    ordering_fields = ("date",)

    ROLES_ECRITURE = ("ADMINISTRATEUR", RH)

    def get_queryset(self):
        queryset = JourFerie.objects.select_related("filiale")

        annee = self.request.query_params.get("annee")
        if annee and annee.isdigit():
            queryset = queryset.filter(date__year=int(annee))

        # Les fériés du groupe (sans filiale) restent visibles de tous.
        return queryset.filter(filiale__isnull=True) | restreindre_a_la_filiale(
            queryset.filter(filiale__isnull=False), self.request.user)

    def get_permissions(self):
        if self.request.method not in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated(), _EcritureJourFerie()]
        return super().get_permissions()


class _EcritureJourFerie(permissions.BasePermission):
    message = "Seuls les RH et l'administrateur modifient les jours fériés."

    def has_permission(self, request, view):
        return request.user.role in JourFerieViewSet.ROLES_ECRITURE
