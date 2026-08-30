from rest_framework import serializers

from .circuits import roles_autorises, seuil_direction
from .models import BonSortie, Caisse, MouvementCaisse


class CaisseSerializer(serializers.ModelSerializer):
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    detenteur_nom = serializers.CharField(
        source="detenteur.nom_complet", read_only=True, default=None)
    solde = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Caisse
        fields = (
            "id", "nom", "code", "filiale", "filiale_nom",
            "detenteur", "detenteur_nom", "description", "active",
            "solde", "date_creation",
        )
        read_only_fields = ("id", "solde", "date_creation")


class MouvementCaisseSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(
        source="get_type_mouvement_display", read_only=True)
    cree_par_nom = serializers.CharField(
        source="cree_par.nom_complet", read_only=True)
    bon_reference = serializers.CharField(
        source="bon_sortie.reference", read_only=True, default=None)

    class Meta:
        model = MouvementCaisse
        fields = (
            "id", "caisse", "type_mouvement", "type_libelle", "montant",
            "justificatif", "reference", "motif",
            "bon_sortie", "bon_reference",
            "cree_par", "cree_par_nom", "date_operation", "date_creation",
        )
        read_only_fields = fields


class AlimentationSerializer(serializers.Serializer):
    """Une alimentation exige une preuve : fichier ou référence."""

    montant = serializers.DecimalField(max_digits=14, decimal_places=2)
    justificatif = serializers.FileField(required=False, allow_null=True)
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    motif = serializers.CharField(required=False, allow_blank=True, default="")
    date_operation = serializers.DateField(required=False, allow_null=True)


class CorrectionSerializer(serializers.Serializer):
    montant = serializers.DecimalField(max_digits=14, decimal_places=2)
    motif = serializers.CharField()
    date_operation = serializers.DateField(required=False, allow_null=True)


class BonSortieSerializer(serializers.ModelSerializer):
    caisse_nom = serializers.CharField(source="caisse.nom", read_only=True)
    demandeur_nom = serializers.CharField(
        source="demandeur.nom_complet", read_only=True)
    destinataire_nom = serializers.CharField(
        source="destinataire.nom_complet", read_only=True, default=None)
    statut_libelle = serializers.CharField(
        source="get_statut_display", read_only=True)
    type_libelle = serializers.CharField(
        source="get_type_depense_display", read_only=True)
    moyen_libelle = serializers.CharField(
        source="get_moyen_transport_display", read_only=True, default="")
    montant_paye = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    montant_rendu = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    montant_consomme = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    exige_justificatif = serializers.BooleanField(read_only=True)

    class Meta:
        model = BonSortie
        fields = (
            "id", "reference", "caisse", "caisse_nom",
            "demandeur", "demandeur_nom", "destinataire", "destinataire_nom",
            "objet", "montant", "type_depense", "type_libelle",
            "moyen_transport", "moyen_libelle", "exige_justificatif",
            "justificatif", "statut", "statut_libelle", "motif_decision",
            "montant_paye", "montant_rendu", "montant_consomme",
            "document", "date_creation",
        )
        read_only_fields = fields


class DepotBonSerializer(serializers.Serializer):
    caisse = serializers.PrimaryKeyRelatedField(queryset=Caisse.objects.all())
    objet = serializers.CharField()
    montant = serializers.DecimalField(max_digits=14, decimal_places=2)
    type_depense = serializers.ChoiceField(choices=BonSortie.TypeDepense.choices)
    moyen_transport = serializers.ChoiceField(
        choices=BonSortie.MoyenTransport.choices, required=False,
        allow_blank=True, default="")
    destinataire = serializers.IntegerField(required=False, allow_null=True)
    justificatif = serializers.FileField(required=False, allow_null=True)


class DecisionBonSerializer(serializers.Serializer):
    autorise = serializers.BooleanField()
    motif = serializers.CharField(required=False, allow_blank=True, default="")


class RetourSerializer(serializers.Serializer):
    montant = serializers.DecimalField(max_digits=14, decimal_places=2)
    motif = serializers.CharField(required=False, allow_blank=True, default="")
    date_operation = serializers.DateField(required=False, allow_null=True)


class ReglesBonSerializer(serializers.Serializer):
    """
    Règles d'adressage, pour que le formulaire affiche le bon niveau
    d'autorisation avant que l'utilisateur ne se trompe.
    """

    @staticmethod
    def regles():
        seuil = seuil_direction()
        return {
            "seuil_direction": str(seuil),
            "roles_sous_seuil": list(roles_autorises(seuil - 1)),
            "roles_au_dessus": list(roles_autorises(seuil + 1)),
            "moyens_avec_justificatif": list(BonSortie.MOYENS_AVEC_HISTORIQUE),
        }
