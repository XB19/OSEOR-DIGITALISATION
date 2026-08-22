from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from applications.journalisation.services import enregistrer_action
from config.permissions import est_direction, restreindre_a_la_filiale
from .models import Document, ConfigurationDocument
from .services import notifier_etape_courante, notifier_decision_finale
from .serializers import (
    DocumentSerializer,
    DocumentEcritureSerializer,
    ConfigurationDocumentSerializer,
    ViserSerializer,
)


class DocumentViewSet(viewsets.ModelViewSet):
    """
    Documents administratifs (Fiche de besoin, Demande d'achat, Fiche de
    transport, Bon de sortie de caisse…). Chaque filiale a sa propre
    configuration de colonnes et de chaîne de visas (ConfigurationDocument).
    """

    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ("type_document", "statut", "filiale")
    ordering_fields = ("date_creation",)
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Document.objects.select_related("filiale", "demandeur")
        return restreindre_a_la_filiale(qs, self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return DocumentEcritureSerializer
        return DocumentSerializer

    def get_serializer_context(self):
        return {"request": self.request}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        enregistrer_action(
            request.user, "DOCUMENT_CREE",
            f"{document.numero} — {document.get_type_document_display()}", objet=document,
        )
        config = document.configuration()
        if config:
            notifier_etape_courante(document, config)
        return Response(
            DocumentSerializer(document, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def viser(self, request, pk=None):
        """
        Appose un visa sur l'étape courante et fait avancer la chaîne.

        Le document est relu et verrouillé (`select_for_update`) à l'intérieur
        d'une transaction : `historique_visas` est un JSONField modifié en
        lecture-modification-écriture, et deux visas simultanés sur des étapes
        voisines s'écrasaient l'un l'autre — le second sauvegardait la liste
        qu'il avait lue avant le premier, effaçant une signature.

        Les notifications sont volontairement émises APRÈS le commit : un
        échec d'envoi ne doit jamais annuler un visa déjà accordé.
        """
        # Validation du corps de requête avant d'ouvrir la transaction :
        # inutile de tenir un verrou pendant qu'on rejette une saisie.
        entree = ViserSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        decision = entree.validated_data["decision"]
        commentaire = entree.validated_data["commentaire"]
        u = request.user

        with transaction.atomic():
            # get_object() applique les permissions et le périmètre de
            # filiale ; la relecture verrouillée qui suit garantit qu'aucun
            # autre visa ne se glisse entre la lecture et l'écriture.
            document = self.get_object()
            document = (
                Document.objects
                .select_for_update()
                .select_related("filiale", "demandeur")
                .get(pk=document.pk)
            )

            config = document.configuration()

            if not config or not config.visas:
                return Response({"detail": "Aucune configuration de visas pour ce document."}, status=400)
            if document.statut != Document.Statut.EN_COURS:
                return Response({"detail": "Ce document a déjà été traité."}, status=400)

            etape = document.etape_visa_courante
            if etape >= len(config.visas):
                return Response({"detail": "Toutes les étapes ont déjà été visées."}, status=400)

            etape_config = config.visas[etape]
            role_requis = etape_config.get("role")
            autorise = est_direction(u) or (role_requis and u.role == role_requis)
            if not autorise:
                return Response(
                    {"detail": "Vous n'êtes pas habilité à viser cette étape."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            document.historique_visas = document.historique_visas + [{
                "etape": etape,
                "cle": etape_config.get("cle"),
                "libelle": etape_config.get("libelle"),
                "utilisateur_id": u.id,
                "utilisateur_nom": u.nom_complet,
                "decision": decision,
                "commentaire": commentaire,
                "date": timezone.now().isoformat(),
                "a_une_signature": bool(u.signature),
            }]

            if decision == "REFUSE":
                document.statut = Document.Statut.REFUSE
                document.motif_rejet = commentaire
            else:
                etape_suivante = etape + 1
                document.etape_visa_courante = etape_suivante
                if etape_suivante >= len(config.visas):
                    document.statut = Document.Statut.VALIDE

            document.save()
            # Le journal fait partie de l'écriture : un visa enregistré sans
            # sa trace d'audit vaut mieux être annulé que conservé.
            enregistrer_action(
                u, "DOCUMENT_VISE",
                f"{document.numero} — {etape_config.get('libelle')} ({decision})", objet=document,
            )

        if document.statut in (Document.Statut.VALIDE, Document.Statut.REFUSE):
            notifier_decision_finale(document, decision, commentaire)
        else:
            notifier_etape_courante(document, config)

        return Response(DocumentSerializer(document, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"])
    def configuration(self, request):
        """Configuration (colonnes + visas) du type de document pour la filiale de l'utilisateur."""
        type_document = request.query_params.get("type_document")
        if not type_document:
            return Response({"detail": "Paramètre type_document requis."}, status=400)
        filiale = request.user.filiale
        if filiale is None:
            return Response(
                {"detail": "Votre compte n'est rattaché à aucune filiale."}, status=400,
            )
        config, _ = ConfigurationDocument.objects.get_or_create(
            filiale=filiale, type_document=type_document,
            defaults={"colonnes": [], "visas": []},
        )
        return Response(ConfigurationDocumentSerializer(config).data)
