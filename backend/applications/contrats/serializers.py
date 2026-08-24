from django.utils import timezone
from rest_framework import serializers

from .models import Contrat, PieceJointeContrat


def _generer_numero(filiale) -> str:
    annee = timezone.now().year
    compte = Contrat.objects.filter(filiale=filiale, date_creation__year=annee).count() + 1
    return f"{filiale.code}-CT-{annee}-{compte:04d}"


class PieceJointeContratSerializer(serializers.ModelSerializer):
    ajoute_par_nom = serializers.CharField(source="ajoute_par.nom_complet", read_only=True)

    class Meta:
        model = PieceJointeContrat
        fields = ("id", "fichier", "nom_original", "ajoute_par", "ajoute_par_nom", "date_ajout")
        read_only_fields = ("ajoute_par", "date_ajout")


class ContratSerializer(serializers.ModelSerializer):
    """Lecture d'un contrat (liste, détail)."""

    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    type_contrat_libelle = serializers.CharField(source="get_type_contrat_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    cree_par_nom = serializers.CharField(source="cree_par.nom_complet", read_only=True)
    jours_avant_echeance = serializers.SerializerMethodField()
    pieces_jointes = PieceJointeContratSerializer(many=True, read_only=True)

    class Meta:
        model = Contrat
        fields = (
            "id", "numero", "filiale", "filiale_nom",
            "intitule", "partie_contractante", "type_contrat", "type_contrat_libelle",
            "reference", "date_debut", "date_echeance", "jours_avant_echeance", "montant",
            "description", "statut", "statut_libelle", "motif_resiliation", "date_resiliation",
            "cree_par", "cree_par_nom", "pieces_jointes",
            "date_creation", "date_modification",
        )
        read_only_fields = fields

    def get_jours_avant_echeance(self, obj):
        return obj.jours_avant_echeance


class ContratEcritureSerializer(serializers.ModelSerializer):
    """
    Création/modification d'un contrat. `filiale`, `cree_par`, `numero` et
    `statut` ne sont jamais fournis par le client : la filiale est toujours
    celle de l'auteur, le statut ne change qu'au travers de l'action
    `resilier` (ou automatiquement à l'échéance, cf. services.py).
    """

    class Meta:
        model = Contrat
        fields = (
            "intitule", "partie_contractante", "type_contrat", "reference",
            "date_debut", "date_echeance", "montant", "description",
        )

    def validate(self, attrs):
        date_debut = attrs.get("date_debut", getattr(self.instance, "date_debut", None))
        date_echeance = attrs.get("date_echeance", getattr(self.instance, "date_echeance", None))
        if date_debut and date_echeance and date_echeance < date_debut:
            raise serializers.ValidationError(
                "La date d'échéance ne peut pas être antérieure à la date de début."
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        filiale = request.user.filiale
        if filiale is None:
            raise serializers.ValidationError(
                "Votre compte n'est rattaché à aucune filiale : impossible d'enregistrer ce contrat."
            )
        return Contrat.objects.create(
            filiale=filiale,
            cree_par=request.user,
            numero=_generer_numero(filiale),
            **validated_data,
        )
