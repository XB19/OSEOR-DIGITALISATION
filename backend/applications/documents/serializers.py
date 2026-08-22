from django.utils import timezone
from rest_framework import serializers

from config.permissions import est_direction
from .models import Document, ConfigurationDocument, TypeDocument

_TYPE_COURT = {
    TypeDocument.FICHE_BESOIN: "FB",
    TypeDocument.DEMANDE_ACHAT: "DA",
    TypeDocument.FICHE_TRANSPORT: "FT",
    TypeDocument.BON_SORTIE_CAISSE: "BSC",
    TypeDocument.NOTE_INTERNE: "NI",
}


def _generer_numero(filiale, type_document) -> str:
    annee = timezone.now().year
    compte = Document.objects.filter(
        filiale=filiale, type_document=type_document, date_creation__year=annee,
    ).count() + 1
    return f"{filiale.code}-{_TYPE_COURT.get(type_document, 'DOC')}-{annee}-{compte:04d}"


class ConfigurationDocumentSerializer(serializers.ModelSerializer):
    type_document_libelle = serializers.CharField(source="get_type_document_display", read_only=True)

    class Meta:
        model = ConfigurationDocument
        fields = ("filiale", "type_document", "type_document_libelle", "colonnes", "visas")


class DocumentSerializer(serializers.ModelSerializer):
    """Lecture d'un document (liste, détail)."""

    type_document_libelle = serializers.CharField(source="get_type_document_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.nom_complet", read_only=True)
    visa_courant = serializers.SerializerMethodField()
    peut_viser = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            "id", "numero", "type_document", "type_document_libelle",
            "filiale", "filiale_nom", "demandeur", "demandeur_nom",
            "champs_entete", "lignes", "montant_total",
            "statut", "statut_libelle", "etape_visa_courante",
            "historique_visas", "motif_rejet", "visa_courant", "peut_viser",
            "date_creation", "date_modification",
        )
        read_only_fields = fields

    def get_visa_courant(self, obj):
        if obj.statut != Document.Statut.EN_COURS:
            return None
        config = obj.configuration()
        if not config or obj.etape_visa_courante >= len(config.visas):
            return None
        return config.visas[obj.etape_visa_courante]

    def get_peut_viser(self, obj) -> bool:
        request = self.context.get("request")
        if not request:
            return False
        etape = self.get_visa_courant(obj)
        if not etape:
            return False
        u = request.user
        if est_direction(u):
            return True
        return bool(etape.get("role")) and u.role == etape["role"]


class DocumentEcritureSerializer(serializers.ModelSerializer):
    """Création d'un document par son demandeur (filiale = celle du demandeur)."""

    class Meta:
        model = Document
        fields = ("type_document", "champs_entete", "lignes", "montant_total")

    def create(self, validated_data):
        request = self.context["request"]
        demandeur = request.user
        filiale = demandeur.filiale
        if filiale is None:
            raise serializers.ValidationError(
                "Votre compte n'est rattaché à aucune filiale : impossible de créer ce document."
            )

        type_document = validated_data["type_document"]
        config, _ = ConfigurationDocument.objects.get_or_create(
            filiale=filiale, type_document=type_document,
            defaults={"colonnes": [], "visas": []},
        )

        document = Document(
            filiale=filiale,
            type_document=type_document,
            demandeur=demandeur,
            champs_entete=validated_data.get("champs_entete", {}),
            lignes=validated_data.get("lignes", []),
            montant_total=validated_data.get("montant_total", 0),
            numero=_generer_numero(filiale, type_document),
        )

        if not config.visas:
            # Aucune chaîne de visas configurée pour cette filiale/type :
            # rien à valider, le document est directement considéré traité.
            document.statut = Document.Statut.VALIDE
        else:
            # Étape 0 = toujours le visa du demandeur, implicite à la soumission.
            document.historique_visas = [{
                "etape": 0,
                "cle": config.visas[0].get("cle"),
                "libelle": config.visas[0].get("libelle"),
                "utilisateur_id": demandeur.id,
                "utilisateur_nom": demandeur.nom_complet,
                "decision": "VALIDE",
                "commentaire": "",
                "date": timezone.now().isoformat(),
                "a_une_signature": bool(demandeur.signature),
            }]
            document.etape_visa_courante = 1
            if len(config.visas) <= 1:
                document.statut = Document.Statut.VALIDE

        document.save()
        return document


class ViserSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("VALIDE", "REFUSE"))
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")
