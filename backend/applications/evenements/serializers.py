from rest_framework import serializers

from .models import Evenement


class EvenementSerializer(serializers.ModelSerializer):
    """Lecture d'un événement (liste, détail, calendrier)."""

    type_libelle = serializers.CharField(
        source="get_type_evenement_display", read_only=True)
    visibilite_libelle = serializers.CharField(
        source="get_visibilite_display", read_only=True)
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    service_nom = serializers.CharField(
        source="service.nom", read_only=True, default=None)
    salle_nom = serializers.CharField(
        source="salle.nom", read_only=True, default=None)
    createur_nom = serializers.CharField(
        source="createur.nom_complet", read_only=True)

    class Meta:
        model = Evenement
        fields = (
            "id", "titre", "type_evenement", "type_libelle", "description",
            "date_debut", "date_fin", "journee_entiere",
            "lieu", "salle", "salle_nom",
            "filiale", "filiale_nom", "service", "service_nom",
            "visibilite", "visibilite_libelle", "photo",
            "createur", "createur_nom",
            "annule", "motif_annulation",
            "date_creation", "date_modification",
        )
        read_only_fields = ("id", "createur", "date_creation", "date_modification")


class EvenementEcritureSerializer(serializers.ModelSerializer):
    """
    Création / modification. `createur` et `filiale` sont déduits de
    l'utilisateur : personne ne saisit d'événement au nom d'un autre, ni
    dans une filiale qui n'est pas la sienne (hors direction).
    """

    class Meta:
        model = Evenement
        fields = (
            "titre", "type_evenement", "description",
            "date_debut", "date_fin", "journee_entiere",
            "lieu", "salle", "filiale", "service", "visibilite", "photo",
            "annule", "motif_annulation",
        )
        extra_kwargs = {"filiale": {"required": False}}

    def validate(self, attributs):
        utilisateur = self.context["request"].user

        filiale = attributs.get("filiale") or getattr(
            self.instance, "filiale", None) or utilisateur.filiale
        if filiale is None:
            raise serializers.ValidationError(
                "Votre compte n'est rattaché à aucune filiale : impossible de "
                "créer un événement."
            )
        attributs["filiale"] = filiale

        # Contrôles métier du modèle (cohérence des dates, service/filiale,
        # visibilité SERVICE sans service) : on les fait remonter en 400.
        instance = Evenement(**{
            **{
                champ: getattr(self.instance, champ, None)
                for champ in ("titre", "date_debut", "date_fin", "visibilite")
            },
            **attributs,
            "createur": utilisateur,
        })
        instance.clean()

        return attributs

    def create(self, donnees_validees):
        donnees_validees["createur"] = self.context["request"].user
        return super().create(donnees_validees)
