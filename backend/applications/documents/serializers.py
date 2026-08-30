import json
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework import serializers

from config.permissions import est_direction
from .models import Document, ConfigurationDocument, TypeDocument

_TYPE_COURT = {
    TypeDocument.FICHE_BESOIN: "FB",
    TypeDocument.DEMANDE_ACHAT: "DA",
    TypeDocument.FICHE_TRANSPORT: "FT",
    TypeDocument.BON_SORTIE_CAISSE: "BSC",
    TypeDocument.BON_COMMANDE: "BC",
    TypeDocument.NOTE_INTERNE: "NI",
    TypeDocument.FACTURE: "FAC",
}


def _generer_numero(filiale, type_document) -> str:
    annee = timezone.now().year
    compte = Document.objects.filter(
        filiale=filiale, type_document=type_document, date_creation__year=annee,
    ).count() + 1
    return f"{filiale.code}-{_TYPE_COURT.get(type_document, 'DOC')}-{annee}-{compte:04d}"


def _decimal(valeur) -> Decimal:
    if valeur in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _calculer_montant_fiche_transport(champs_entete: dict, lignes: list) -> Decimal:
    """
    Indemnité kilométrique = (km facturés × taux au km) + total des frais de
    parking. Les km facturés sont recalculés ligne par ligne depuis
    km_fin - km_debut (jamais depuis une "différence" envoyée par le client).
    """
    taux = _decimal(champs_entete.get("taux_auto") if isinstance(champs_entete, dict) else None)
    total_km = Decimal("0")
    total_parking = Decimal("0")
    for ligne in lignes:
        if not isinstance(ligne, dict):
            continue
        difference = _decimal(ligne.get("km_fin")) - _decimal(ligne.get("km_debut"))
        if difference > 0:
            total_km += difference
        total_parking += _decimal(ligne.get("frais_parking"))
    return (total_km * taux) + total_parking


def _calculer_montant_total(type_document, colonnes, lignes, champs_entete) -> Decimal:
    """
    Recalcule le montant total côté serveur — jamais fait confiance à une
    valeur envoyée par le client.
    """
    if type_document == TypeDocument.FICHE_TRANSPORT:
        return _calculer_montant_fiche_transport(champs_entete, lignes)

    # Types génériques (tableau configurable) : ne somme que si la filiale a
    # prévu une colonne "montant" (les fiches "quantité" n'en ont pas).
    if not any(c.get("cle") == "montant" for c in colonnes):
        return Decimal("0")
    total = Decimal("0")
    for ligne in lignes:
        if isinstance(ligne, dict):
            total += _decimal(ligne.get("montant"))
    return total


class ConfigurationDocumentSerializer(serializers.ModelSerializer):
    type_document_libelle = serializers.CharField(source="get_type_document_display", read_only=True)
    configure = serializers.BooleanField(read_only=True)

    class Meta:
        model = ConfigurationDocument
        fields = ("filiale", "type_document", "type_document_libelle", "colonnes", "visas", "configure")


class DocumentSerializer(serializers.ModelSerializer):
    """Lecture d'un document (liste, détail)."""

    type_document_libelle = serializers.CharField(source="get_type_document_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.nom_complet", read_only=True)
    document_source_numero = serializers.CharField(source="document_source.numero", read_only=True, default=None)
    documents_derives_numeros = serializers.SerializerMethodField()
    visa_courant = serializers.SerializerMethodField()
    peut_viser = serializers.SerializerMethodField()
    statut_paiement = serializers.CharField(read_only=True)
    echeance_depassee = serializers.BooleanField(read_only=True)

    class Meta:
        model = Document
        fields = (
            "id", "numero", "type_document", "type_document_libelle",
            "filiale", "filiale_nom", "demandeur", "demandeur_nom",
            "champs_entete", "lignes", "montant_total", "piece_jointe",
            "document_source", "document_source_numero", "documents_derives_numeros",
            "statut", "statut_libelle", "etape_visa_courante",
            "historique_visas", "motif_rejet", "visa_courant", "peut_viser",
            "statut_paiement", "echeance_depassee",
            "date_creation", "date_modification",
        )
        read_only_fields = fields

    def get_documents_derives_numeros(self, obj):
        return list(obj.documents_derives.values_list("numero", flat=True))

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


class ChampJSONSouple(serializers.JSONField):
    """
    JSONField tolérant : accepte un objet déjà décodé (requête JSON classique)
    ou une chaîne JSON (requête multipart/form-data — dès qu'une pièce jointe
    est envoyée, tout le reste du formulaire voyage en texte, y compris les
    champs qui sont en réalité des objets/tableaux).
    """

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (ValueError, TypeError):
                self.fail("invalid")
        return super().to_internal_value(data)


class DocumentEcritureSerializer(serializers.ModelSerializer):
    """
    Création d'un document par son demandeur (filiale = celle du demandeur).
    `montant_total` n'est pas un champ accepté en entrée : il est toujours
    recalculé côté serveur à partir des lignes (voir `_calculer_montant_total`).
    """

    champs_entete = ChampJSONSouple(required=False)
    lignes = ChampJSONSouple(required=False)
    piece_jointe = serializers.FileField(required=False, allow_null=True)
    document_source = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(), required=False, allow_null=True,
        help_text="Ex. la Demande d'achat validée à l'origine d'un Bon de commande.",
    )

    class Meta:
        model = Document
        fields = ("type_document", "champs_entete", "lignes", "piece_jointe", "document_source")

    #: Types qu'on ne saisit plus directement : ils sont engendrés par le
    #: module qui en détient la vérité. Un bon de sortie de caisse naît
    #: d'une demande sur une caisse (montant, autorisation, décaissement) ;
    #: le laisser créer à la main produirait deux bons de sortie
    #: concurrents, dont l'un ne toucherait aucune caisse.
    TYPES_ENGENDRES = {TypeDocument.BON_SORTIE_CAISSE: "/api/bons-sortie/"}

    def create(self, validated_data):
        request = self.context["request"]
        demandeur = request.user

        type_demande = validated_data["type_document"]
        if type_demande in self.TYPES_ENGENDRES:
            raise serializers.ValidationError(
                f"Un {TypeDocument(type_demande).label.lower()} se crée depuis "
                f"la caisse ({self.TYPES_ENGENDRES[type_demande]}) : la pièce "
                f"imprimable est engendrée au décaissement."
            )
        filiale = demandeur.filiale
        if filiale is None:
            raise serializers.ValidationError(
                "Votre compte n'est rattaché à aucune filiale : impossible de créer ce document."
            )

        type_document = validated_data["type_document"]
        config = ConfigurationDocument.objects.filter(
            filiale=filiale, type_document=type_document,
        ).first()
        if config is None:
            raise serializers.ValidationError(
                "Ce type de document n'est pas encore configuré pour votre filiale. "
                "Contactez un administrateur pour le configurer avant de le soumettre."
            )

        document_source = validated_data.get("document_source")
        if document_source is not None:
            if type_document != TypeDocument.BON_COMMANDE:
                raise serializers.ValidationError("Un document source ne peut être lié qu'à un Bon de commande.")
            if document_source.type_document != TypeDocument.DEMANDE_ACHAT:
                raise serializers.ValidationError("Le document lié doit être une Demande d'achat.")
            if document_source.filiale_id != filiale.id:
                raise serializers.ValidationError("Le document lié doit appartenir à votre filiale.")
            if document_source.statut != Document.Statut.VALIDE:
                raise serializers.ValidationError("La Demande d'achat liée doit d'abord être validée.")

        lignes = validated_data.get("lignes", [])
        champs_entete = validated_data.get("champs_entete", {})
        document = Document(
            filiale=filiale,
            type_document=type_document,
            demandeur=demandeur,
            champs_entete=champs_entete,
            lignes=lignes,
            montant_total=_calculer_montant_total(type_document, config.colonnes, lignes, champs_entete),
            piece_jointe=validated_data.get("piece_jointe"),
            document_source=document_source,
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
