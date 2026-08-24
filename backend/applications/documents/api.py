from django.http import HttpResponse
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from applications.journalisation.services import enregistrer_action
from applications.notifications.services import envoyer_notification
from config.permissions import est_direction, restreindre_a_la_filiale
from .models import Document, ConfigurationDocument, TypeDocument
from .services import notifier_etape_courante, notifier_decision_finale
from .pdf import generer_pdf_document
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

    @action(detail=True, methods=["post"])
    def statut_livraison(self, request, pk=None):
        """
        Suivi post-approbation d'un Bon de commande (Émission et suivi) :
        met à jour le statut de livraison auprès du fournisseur. N'ouvre pas
        de porte générale à l'édition des documents — n'affecte que cette
        seule information de suivi, sur un Bon de commande déjà validé.
        """
        document = self.get_object()
        if document.type_document != TypeDocument.BON_COMMANDE:
            return Response({"detail": "Action réservée aux bons de commande."}, status=400)
        if document.statut != Document.Statut.VALIDE:
            return Response(
                {"detail": "Le bon de commande doit être validé avant de suivre sa livraison."}, status=400,
            )

        u = request.user
        autorise = est_direction(u) or (
            u.role == "SECRETAIRE" and u.filiale_id == document.filiale_id
        )
        if not autorise:
            return Response(
                {"detail": "Vous n'êtes pas habilité à mettre à jour ce suivi."},
                status=status.HTTP_403_FORBIDDEN,
            )

        nouveau_statut = request.data.get("statut_livraison")
        valeurs_valides = dict(Document.StatutLivraison.choices)
        if nouveau_statut not in valeurs_valides:
            return Response({"detail": "Statut de livraison invalide."}, status=400)

        champs = dict(document.champs_entete or {})
        champs["statut_livraison"] = nouveau_statut
        document.champs_entete = champs
        document.save(update_fields=["champs_entete", "date_modification"])

        enregistrer_action(
            u, "BON_COMMANDE_SUIVI",
            f"{document.numero} — {valeurs_valides[nouveau_statut]}", objet=document,
        )
        envoyer_notification(
            document.demandeur, "Suivi de votre bon de commande",
            f"{document.numero} — {valeurs_valides[nouveau_statut]}", "INFO", objet=document,
        )
        return Response(DocumentSerializer(document, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """
        Version imprimable/archivable du document : circuit de validation et
        signatures scannées inclus. `get_object()` applique déjà le même
        périmètre (filiale) que la consultation normale du document.
        """
        document = self.get_object()
        contenu = generer_pdf_document(document)
        reponse = HttpResponse(contenu, content_type="application/pdf")
        reponse["Content-Disposition"] = f'attachment; filename="{document.numero}.pdf"'
        return reponse

    @action(detail=False, methods=["get"])
    def dernier_km(self, request):
        """
        Dernier relevé "km_actuel" connu de l'utilisateur, pour pré-remplir
        "Km précédent" d'une nouvelle fiche de transport (continuité du
        compteur d'un mois sur l'autre).
        """
        recents = Document.objects.filter(
            demandeur=request.user, type_document=TypeDocument.FICHE_TRANSPORT,
        ).order_by("-date_creation")[:20]

        km = None
        for doc in recents:
            valeur = doc.champs_entete.get("km_actuel") if isinstance(doc.champs_entete, dict) else None
            if valeur not in (None, ""):
                km = valeur
                break
        return Response({"km_actuel": km})

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
        config = ConfigurationDocument.objects.filter(
            filiale=filiale, type_document=type_document,
        ).first()
        if config is None:
            # Ne pas persister une configuration vide juste parce qu'on l'a
            # consultée : un document créé ensuite doit être bloqué (et non
            # auto-validé) tant qu'un administrateur ne l'a pas réellement
            # configurée (colonnes + visas).
            config = ConfigurationDocument(filiale=filiale, type_document=type_document)
        return Response(ConfigurationDocumentSerializer(config).data)
