from rest_framework import serializers

from .models import JalonPrestation, Prestation
from . import services


class JalonPrestationSerializer(serializers.ModelSerializer):
    realise = serializers.BooleanField(read_only=True)

    class Meta:
        model = JalonPrestation
        fields = (
            "id", "prestation", "intitule", "date_prevue",
            "date_realisation", "realise", "commentaire",
        )
        read_only_fields = ("id", "realise")


class PrestationSerializer(serializers.ModelSerializer):
    """Lecture d'une prestation, avec son avancement calculé."""

    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    service_nom = serializers.CharField(source="service.nom", read_only=True)
    responsable_nom = serializers.CharField(
        source="responsable.nom_complet", read_only=True)
    statut_libelle = serializers.CharField(
        source="get_statut_display", read_only=True)
    en_retard = serializers.BooleanField(read_only=True)
    avancement = serializers.SerializerMethodField()
    jalons = JalonPrestationSerializer(many=True, read_only=True)

    class Meta:
        model = Prestation
        fields = (
            "id", "reference", "intitule", "client", "description",
            "filiale", "filiale_nom", "service", "service_nom",
            "responsable", "responsable_nom", "intervenants",
            "date_debut", "date_fin_prevue", "date_fin_reelle",
            "montant", "statut", "statut_libelle",
            "en_retard", "avancement", "jalons",
            "date_creation", "date_modification",
        )
        read_only_fields = (
            "id", "reference", "date_creation", "date_modification")

    def get_avancement(self, obj):
        return services.avancement(obj)


class PrestationEcritureSerializer(serializers.ModelSerializer):
    """
    Création / modification. La filiale se déduit du service : les deux
    doivent concorder, autant n'en demander qu'une.
    """

    class Meta:
        model = Prestation
        fields = (
            "intitule", "client", "description", "service", "responsable",
            "intervenants", "date_debut", "date_fin_prevue",
            "date_fin_reelle", "montant", "statut",
        )

    def validate(self, attributs):
        service = attributs.get("service") or getattr(
            self.instance, "service", None)
        if service is None:
            raise serializers.ValidationError(
                {"service": "Le service réalisateur est obligatoire."})

        attributs["filiale"] = service.filiale

        instance = Prestation(**{
            **{
                champ: getattr(self.instance, champ, None)
                for champ in ("date_debut", "date_fin_prevue", "date_fin_reelle")
            },
            **{c: v for c, v in attributs.items() if c != "intervenants"},
        })
        instance.clean()

        return attributs
