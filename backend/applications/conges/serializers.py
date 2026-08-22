from rest_framework import serializers

from .models import DemandeConge, JourFerie, MouvementConge


class DemandeCongeSerializer(serializers.ModelSerializer):
    """Lecture d'une demande de congé."""

    utilisateur_nom = serializers.CharField(
        source="utilisateur.nom_complet", read_only=True)
    type_libelle = serializers.CharField(
        source="get_type_conge_display", read_only=True)
    statut_libelle = serializers.CharField(
        source="get_statut_display", read_only=True)
    valideur_nom = serializers.CharField(
        source="valideur.nom_complet", read_only=True, default=None)

    class Meta:
        model = DemandeConge
        fields = (
            "id", "utilisateur", "utilisateur_nom",
            "type_conge", "type_libelle",
            "date_debut", "date_fin", "jours_ouvres", "motif",
            "statut", "statut_libelle",
            "valideur", "valideur_nom", "date_decision", "motif_decision",
            "date_creation",
        )
        read_only_fields = fields


class DepotDemandeSerializer(serializers.Serializer):
    """Dépôt d'une demande. Les jours ouvrés sont calculés, jamais saisis."""

    type_conge = serializers.ChoiceField(
        choices=DemandeConge._meta.get_field("type_conge").choices)
    date_debut = serializers.DateField()
    date_fin = serializers.DateField()
    motif = serializers.CharField(required=False, allow_blank=True, default="")


class DecisionSerializer(serializers.Serializer):
    approuvee = serializers.BooleanField()
    motif = serializers.CharField(required=False, allow_blank=True, default="")


class AnnulationSerializer(serializers.Serializer):
    motif = serializers.CharField(required=False, allow_blank=True, default="")


class MouvementCongeSerializer(serializers.ModelSerializer):
    """Ligne du registre : d'où vient chaque jour."""

    type_libelle = serializers.CharField(
        source="get_type_mouvement_display", read_only=True)

    class Meta:
        model = MouvementConge
        fields = (
            "id", "annee", "type_mouvement", "type_libelle",
            "jours", "date_effet", "demande", "motif", "date_creation",
        )
        read_only_fields = fields


class JourFerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = JourFerie
        fields = ("id", "date", "nom", "filiale")
