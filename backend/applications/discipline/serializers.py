from rest_framework import serializers

from .convention import BAREME, FAUTES_LOURDES, DELAI_SANCTION_MOIS
from .models import ExplicationSalarie, ProcedureDisciplinaire, Sanction


class ExplicationSerializer(serializers.ModelSerializer):
    mode_libelle = serializers.CharField(source="get_mode_display", read_only=True)
    consignee_par_nom = serializers.CharField(
        source="consignee_par.nom_complet", read_only=True)

    class Meta:
        model = ExplicationSalarie
        fields = (
            "id", "procedure", "mode", "mode_libelle", "contenu",
            "piece_jointe", "delegue_present",
            "consignee_par", "consignee_par_nom", "date_explication",
        )
        read_only_fields = fields


class SanctionSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(
        source="get_type_sanction_display", read_only=True)
    prononcee_par_nom = serializers.CharField(
        source="prononcee_par.nom_complet", read_only=True)
    formalites_completes = serializers.BooleanField(read_only=True)

    class Meta:
        model = Sanction
        fields = (
            "id", "procedure", "type_sanction", "type_libelle", "duree_jours",
            "motif", "prononcee_par", "prononcee_par_nom", "date_prononce",
            "date_notification", "date_inspection_travail",
            "formalites_completes", "date_creation",
        )
        read_only_fields = fields


class ProcedureSerializer(serializers.ModelSerializer):
    salarie_nom = serializers.CharField(
        source="salarie.nom_complet", read_only=True)
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    statut_libelle = serializers.CharField(
        source="get_statut_display", read_only=True)
    qualification_libelle = serializers.CharField(
        source="get_qualification_display", read_only=True)
    ouverte_par_nom = serializers.CharField(
        source="ouverte_par.nom_complet", read_only=True)
    date_limite_sanction = serializers.DateField(read_only=True)
    delai_depasse = serializers.BooleanField(read_only=True)
    explications_recueillies = serializers.BooleanField(read_only=True)
    explications = ExplicationSerializer(many=True, read_only=True)
    sanction = SanctionSerializer(read_only=True)

    class Meta:
        model = ProcedureDisciplinaire
        fields = (
            "id", "reference", "salarie", "salarie_nom",
            "filiale", "filiale_nom", "faits", "date_faits", "date_preuve",
            "qualification", "qualification_libelle", "faute_lourde_invoquee",
            "statut", "statut_libelle",
            "mise_a_pied_conservatoire", "date_mise_a_pied",
            "date_limite_sanction", "delai_depasse",
            "explications_recueillies", "explications", "sanction",
            "ouverte_par", "ouverte_par_nom", "motif_classement",
            "date_ouverture",
        )
        read_only_fields = fields


class OuvertureSerializer(serializers.Serializer):
    salarie = serializers.IntegerField()
    faits = serializers.CharField()
    date_faits = serializers.DateField()
    date_preuve = serializers.DateField()
    qualification = serializers.ChoiceField(
        choices=ProcedureDisciplinaire.Qualification.choices,
        default=ProcedureDisciplinaire.Qualification.FAUTE_SIMPLE)
    faute_lourde_invoquee = serializers.CharField(
        required=False, allow_blank=True, default="")
    mise_a_pied_conservatoire = serializers.BooleanField(default=False)


class ConsignationSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=ExplicationSalarie.Mode.choices)
    contenu = serializers.CharField(required=False, allow_blank=True, default="")
    delegue_present = serializers.BooleanField(default=False)
    piece_jointe = serializers.FileField(required=False, allow_null=True)


class PrononceSerializer(serializers.Serializer):
    type_sanction = serializers.ChoiceField(choices=list(BAREME.keys()))
    motif = serializers.CharField()
    duree_jours = serializers.IntegerField(required=False, allow_null=True)
    date_prononce = serializers.DateField(required=False, allow_null=True)


class FormalitesSerializer(serializers.Serializer):
    date_notification = serializers.DateField(required=False, allow_null=True)
    date_inspection_travail = serializers.DateField(
        required=False, allow_null=True)


class ClassementSerializer(serializers.Serializer):
    motif = serializers.CharField()


class BaremeDisciplinaireSerializer(serializers.Serializer):
    """Barème de l'article 58, pour que l'écran affiche les bornes réelles."""

    @staticmethod
    def bareme():
        return {
            "delai_mois": DELAI_SANCTION_MOIS,
            "sanctions": [
                {
                    "code": code,
                    "libelle": r["libelle"],
                    "rang": r["rang"],
                    "jours_min": r["jours_min"],
                    "jours_max": r["jours_max"],
                    "faute_lourde_requise": r["faute_lourde_requise"],
                }
                for code, r in sorted(
                    BAREME.items(), key=lambda item: item[1]["rang"])
            ],
            "fautes_lourdes": [
                {"code": code, "libelle": libelle}
                for code, libelle in FAUTES_LOURDES
            ],
        }
