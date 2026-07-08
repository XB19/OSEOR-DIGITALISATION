from rest_framework import serializers

from .models import Audience, EchangeAudience, Delegation


class EchangeAudienceSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(source="auteur.nom_complet", read_only=True)

    class Meta:
        model = EchangeAudience
        fields = ("id", "audience", "auteur", "auteur_nom", "commentaire", "date_creation")
        read_only_fields = ("auteur", "date_creation")


class DelegationSerializer(serializers.ModelSerializer):
    delegue_nom = serializers.CharField(source="delegue.nom_complet", read_only=True)
    delegue_email = serializers.CharField(source="delegue.email", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Delegation
        fields = (
            "id",
            "audience",
            "delegue",
            "delegue_nom",
            "delegue_email",
            "commentaire",
            "statut",
            "statut_libelle",
            "date_proposition",
            "date_prise_en_compte",
        )
        read_only_fields = ("statut", "date_proposition", "date_prise_en_compte")


class AudienceSerializer(serializers.ModelSerializer):
    echanges = EchangeAudienceSerializer(many=True, read_only=True)
    delegations = DelegationSerializer(many=True, read_only=True)
    nom_complet = serializers.CharField(read_only=True)
    dg_nom = serializers.CharField(source="dg.nom_complet", read_only=True)
    secretaire_nom = serializers.CharField(source="secretaire.nom_complet", read_only=True)
    salle_nom = serializers.CharField(source="salle.nom", read_only=True, default=None)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Audience
        fields = (
            "id",
            "nom",
            "prenom",
            "nom_complet",
            "profession",
            "contact",
            "objet_visite",
            "secretaire",
            "secretaire_nom",
            "dg",
            "dg_nom",
            "statut",
            "statut_libelle",
            "date_souhaitee",
            "heure_debut",
            "heure_fin",
            "salle",
            "salle_nom",
            "lieu",
            "reservation",
            "date_confirmation",
            "echanges",
            "delegations",
            "date_creation",
        )
        read_only_fields = (
            "secretaire",
            "statut",
            "reservation",
            "date_confirmation",
            "date_creation",
        )
