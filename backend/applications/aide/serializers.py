from rest_framework import serializers

from .models import EntreeAide


class EntreeAideSerializer(serializers.ModelSerializer):
    module_libelle = serializers.CharField(source="get_module_display", read_only=True)

    class Meta:
        model = EntreeAide
        fields = (
            "id",
            "module",
            "module_libelle",
            "question",
            "mots_cles",
            "reponse",
            "ordre",
            "actif",
        )
