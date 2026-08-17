from rest_framework import serializers

from .models import JournalAction


class JournalActionSerializer(serializers.ModelSerializer):
    acteur_nom = serializers.CharField(source="acteur.nom_complet", read_only=True, default=None)

    class Meta:
        model = JournalAction
        fields = (
            "id",
            "acteur",
            "acteur_nom",
            "action",
            "cible",
            "objet_type",
            "objet_id",
            "details",
            "date_creation",
        )
        read_only_fields = fields
