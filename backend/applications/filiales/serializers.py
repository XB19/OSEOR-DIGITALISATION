from rest_framework import serializers

from .models import Filiale, ParametreFiliale, Service


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


class ServiceSerializer(serializers.ModelSerializer):
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    chef_nom = serializers.CharField(source="chef.nom_complet", read_only=True, default=None)
    nb_membres = serializers.IntegerField(source="membres.count", read_only=True)

    class Meta:
        model = Service
        fields = (
            "id",
            "nom",
            "code",
            "filiale",
            "filiale_nom",
            "chef",
            "chef_nom",
            "description",
            "actif",
            "nb_membres",
        )
