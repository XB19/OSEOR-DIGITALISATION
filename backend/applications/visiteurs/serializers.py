from rest_framework import serializers

from .models import Visite


class VisiteSerializer(serializers.ModelSerializer):
    enregistre_par_nom = serializers.CharField(source="enregistre_par.nom_complet", read_only=True)
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)

    class Meta:
        model = Visite
        fields = (
            "id",
            "nom",
            "prenom",
            "numero_piece",
            "filiale",
            "filiale_nom",
            "enregistre_par",
            "enregistre_par_nom",
            "heure_arrivee",
            "heure_depart",
            "presente",
        )
        read_only_fields = (
            "filiale", "enregistre_par", "heure_arrivee", "heure_depart", "presente",
        )
