from rest_framework import serializers

from .imagerie import valider_image
from .models import Album, Photo


class PhotoSerializer(serializers.ModelSerializer):
    televersee_par_nom = serializers.CharField(
        source="televersee_par.nom_complet", read_only=True)

    class Meta:
        model = Photo
        fields = (
            "id", "album", "image", "miniature", "legende",
            "largeur", "hauteur", "taille_octets",
            "televersee_par", "televersee_par_nom", "date_creation",
        )
        read_only_fields = (
            "id", "miniature", "largeur", "hauteur", "taille_octets",
            "televersee_par", "date_creation",
        )

    def validate_image(self, fichier):
        """
        Contrôle l'en-tête réel du fichier, pas son extension : les deux
        sont fournies par le client, seule la première fait foi.
        """
        valider_image(fichier)
        return fichier


class AlbumSerializer(serializers.ModelSerializer):
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    service_nom = serializers.CharField(
        source="service.nom", read_only=True, default=None)
    evenement_titre = serializers.CharField(
        source="evenement.titre", read_only=True, default=None)
    createur_nom = serializers.CharField(
        source="createur.nom_complet", read_only=True)
    visibilite_libelle = serializers.CharField(
        source="get_visibilite_display", read_only=True)
    nb_photos = serializers.IntegerField(read_only=True)
    couverture = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = (
            "id", "titre", "description",
            "filiale", "filiale_nom", "service", "service_nom",
            "evenement", "evenement_titre",
            "visibilite", "visibilite_libelle", "date_evenement",
            "createur", "createur_nom", "nb_photos", "couverture",
            "date_creation", "date_modification",
        )
        read_only_fields = (
            "id", "createur", "date_creation", "date_modification")

    def get_couverture(self, obj):
        """Vignette de la première photo, pour l'affichage en grille."""
        premiere = obj.photos.first()
        if premiere is None or not premiere.miniature:
            return None

        requete = self.context.get("request")
        url = premiere.miniature.url
        return requete.build_absolute_uri(url) if requete else url


class AlbumEcritureSerializer(serializers.ModelSerializer):
    """La filiale se déduit de l'utilisateur, comme pour les événements."""

    class Meta:
        model = Album
        fields = (
            "titre", "description", "filiale", "service", "evenement",
            "visibilite", "date_evenement",
        )
        extra_kwargs = {"filiale": {"required": False}}

    def validate(self, attributs):
        utilisateur = self.context["request"].user

        filiale = attributs.get("filiale") or getattr(
            self.instance, "filiale", None) or utilisateur.filiale
        if filiale is None:
            raise serializers.ValidationError(
                "Votre compte n'est rattaché à aucune filiale : impossible de "
                "créer un album."
            )
        attributs["filiale"] = filiale

        instance = Album(**{
            **{
                champ: getattr(self.instance, champ, None)
                for champ in ("titre", "visibilite")
            },
            **attributs,
            "createur": utilisateur,
        })
        instance.clean()

        return attributs
