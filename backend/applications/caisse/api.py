from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from config.permissions import LectureTousEcriture, est_direction

from .models import BonSortie, Caisse, MouvementCaisse
from .serializers import (
    AlimentationSerializer, BonSortieSerializer, CaisseSerializer,
    CorrectionSerializer, DecisionBonSerializer, DepotBonSerializer,
    MouvementCaisseSerializer, ReglesBonSerializer, RetourSerializer,
)
from . import services
from .services import OperationRefusee

User = get_user_model()


class CaisseViewSet(viewsets.ModelViewSet):
    """
    Caisses du groupe. Lecture pour la filiale, création réservée à
    l'administration : ouvrir une caisse est un acte de gestion.
    """

    serializer_class = CaisseSerializer
    permission_classes = [LectureTousEcriture("ADMINISTRATEUR", "DIRECTEUR")]
    filterset_fields = ("filiale", "active", "detenteur")
    search_fields = ("nom", "code")
    ordering_fields = ("nom",)

    def get_queryset(self):
        return services.caisses_visibles(self.request.user)

    def get_permissions(self):
        # La permission de classe regit la GESTION des caisses : en ouvrir
        # une releve de l'administration. Les ecritures, elles, sont
        # arbitrees par le service (peut_tenir), qui connait le detenteur
        # de CETTE caisse — sans quoi un caissier ne pourrait pas alimenter
        # la sienne.
        if self.action in ("alimenter", "corriger", "registre"):
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    @action(detail=True, methods=["post"],
            parser_classes=[MultiPartParser, FormParser])
    def alimenter(self, request, pk=None):
        """Fait entrer de l'argent — preuve obligatoire."""
        entree = AlimentationSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            mouvement = services.alimenter(
                self.get_object(),
                entree.validated_data["montant"],
                request.user,
                justificatif=entree.validated_data.get("justificatif"),
                reference=entree.validated_data.get("reference", ""),
                motif=entree.validated_data.get("motif", ""),
                jour=entree.validated_data.get("date_operation"),
            )
        except OperationRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(
            MouvementCaisseSerializer(mouvement).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def corriger(self, request, pk=None):
        """Constate un écart de caisse par une écriture, jamais par retouche."""
        entree = CorrectionSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            mouvement = services.corriger(
                self.get_object(), entree.validated_data["montant"],
                request.user, entree.validated_data["motif"],
                entree.validated_data.get("date_operation"))
        except OperationRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(
            MouvementCaisseSerializer(mouvement).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def registre(self, request, pk=None):
        """Mouvements de la caisse : d'où vient chaque franc."""
        mouvements = (self.get_object().mouvements
                      .select_related("cree_par", "bon_sortie")
                      .all()[:500])
        return Response(MouvementCaisseSerializer(mouvements, many=True).data)


class BonSortieViewSet(mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       viewsets.GenericViewSet):
    """
    Bons de sortie de caisse.

    Lecture seule côté REST classique : le parcours passe par les actions
    dédiées, parce qu'un bon n'est pas un formulaire éditable mais une
    suite de décisions tracées.
    """

    serializer_class = BonSortieSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("caisse", "statut", "type_depense", "destinataire")
    search_fields = ("reference", "objet")
    ordering_fields = ("date_creation", "montant")

    def get_queryset(self):
        utilisateur = self.request.user
        queryset = BonSortie.objects.select_related(
            "caisse", "demandeur", "destinataire")

        if est_direction(utilisateur):
            return queryset

        caisses = services.caisses_visibles(utilisateur)

        # Chacun voit ses bons et ceux qu'il doit autoriser ; le détenteur
        # et les comptables voient ceux de leurs caisses.
        from django.db.models import Q

        perimetre = Q(demandeur=utilisateur) | Q(destinataire=utilisateur)
        if utilisateur.role == "COMPTABLE" or caisses.filter(
            detenteur=utilisateur
        ).exists():
            perimetre |= Q(caisse__in=caisses)

        return queryset.filter(perimetre).distinct()

    def create(self, request, *args, **kwargs):
        entree = DepotBonSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        destinataire = None
        identifiant = entree.validated_data.get("destinataire")
        if identifiant:
            destinataire = User.objects.filter(pk=identifiant).first()
            if destinataire is None:
                return Response(
                    {"detail": "Destinataire introuvable."}, status=400)

        try:
            bon = services.deposer(
                entree.validated_data["caisse"], request.user,
                entree.validated_data["objet"],
                entree.validated_data["montant"],
                entree.validated_data["type_depense"],
                entree.validated_data.get("moyen_transport", ""),
                destinataire,
                entree.validated_data.get("justificatif"),
            )
        except OperationRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(
            BonSortieSerializer(bon).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def decider(self, request, pk=None):
        """Le destinataire autorise ou refuse la dépense."""
        entree = DecisionBonSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            bon = services.decider(
                self.get_object(), request.user,
                entree.validated_data["autorise"],
                entree.validated_data.get("motif", ""))
        except OperationRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(BonSortieSerializer(bon).data)

    @action(detail=True, methods=["post"])
    def payer(self, request, pk=None):
        """Sort effectivement l'argent de la caisse."""
        try:
            bon = services.payer(self.get_object(), request.user)
        except OperationRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        return Response(BonSortieSerializer(bon).data)

    @action(detail=True, methods=["post"])
    def rendre(self, request, pk=None):
        """Remet en caisse la monnaie non dépensée."""
        entree = RetourSerializer(data=request.data)
        entree.is_valid(raise_exception=True)

        try:
            services.rendre_monnaie(
                self.get_object(), entree.validated_data["montant"],
                request.user, entree.validated_data.get("motif", ""),
                entree.validated_data.get("date_operation"))
        except OperationRefusee as erreur:
            return Response({"detail": str(erreur)}, status=400)

        bon = self.get_object()
        bon.refresh_from_db()
        return Response(BonSortieSerializer(bon).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """
        Bon de sortie au format imprimable.

        Le PDF est produit à partir de la pièce engendrée au décaissement :
        aucun format spécifique à maintenir ici, c'est le générateur du
        moteur documentaire qui s'en charge.
        """
        from applications.documents.pdf import generer_pdf_document

        bon = self.get_object()

        if not bon.document_id:
            return Response(
                {"detail": "La pièce imprimable est engendrée au "
                           "décaissement : ce bon n'a pas encore été payé."},
                status=400)

        contenu = generer_pdf_document(bon.document)
        reponse = HttpResponse(contenu, content_type="application/pdf")
        reponse["Content-Disposition"] = (
            f'inline; filename="{bon.reference}.pdf"')
        return reponse

    @action(detail=False, methods=["get"])
    def a_autoriser(self, request):
        """Bons en attente de la décision de l'utilisateur connecté."""
        bons = self.get_queryset().filter(
            statut=BonSortie.Statut.EN_ATTENTE,
        ).exclude(demandeur=request.user)

        if not est_direction(request.user):
            bons = bons.filter(destinataire=request.user)

        return Response(BonSortieSerializer(bons, many=True).data)

    @action(detail=False, methods=["get"])
    def regles(self, request):
        """Seuil d'autorisation et moyens exigeant un justificatif."""
        return Response(ReglesBonSerializer.regles())
