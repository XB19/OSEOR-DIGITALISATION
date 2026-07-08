from rest_framework import serializers

from .models import Filiale, ParametreFiliale


class ParametreFilialeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametreFiliale
        fields = (
            "delai_min_reservation",
            "duree_max_reservation",
            "nb_max_reservations_actives",
            "delai_annulation",
        )


class FilialeSerializer(serializers.ModelSerializer):
    parametres = ParametreFilialeSerializer(read_only=True)

    class Meta:
        model = Filiale
        fields = (
            "id",
            "nom",
            "code",
            "description",
            "email",
            "telephone",
            "adresse",
            "active",
            "parametres",
        )
