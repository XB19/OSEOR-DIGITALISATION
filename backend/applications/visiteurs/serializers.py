from rest_framework import serializers

from .models import Visite, _VALIDATEUR_NUMERO_PIECE


class VisiteSerializer(serializers.ModelSerializer):
    # Forcés `required` malgré le `default=""` en base (nécessaire côté
    # modèle uniquement pour ne pas bloquer une future migration). Le
    # validateur n'est pas hérité automatiquement dès qu'un champ est
    # redéclaré explicitement : on le reprend donc ici.
    numero_piece = serializers.CharField(max_length=30, validators=[_VALIDATEUR_NUMERO_PIECE])
    motif = serializers.CharField(max_length=255)

    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    enregistre_par_nom = serializers.CharField(source="enregistre_par.nom_complet", read_only=True)
    traite_par_nom = serializers.CharField(source="traite_par.nom_complet", read_only=True, default=None)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Visite
        fields = (
            "id",
            "nom",
            "prenom",
            "numero_piece",
            "motif",
            "filiale",
            "filiale_nom",
            "enregistre_par",
            "enregistre_par_nom",
            "traite_par",
            "traite_par_nom",
            "statut",
            "statut_libelle",
            "motif_refus",
            "heure_arrivee",
            "heure_depart",
        )
        read_only_fields = (
            "filiale", "enregistre_par", "traite_par",
            "statut", "motif_refus", "heure_arrivee", "heure_depart",
        )

    def validate(self, attrs):
        request = self.context.get("request")
        utilisateur = request.user if request else None
        if utilisateur and not utilisateur.filiale_id:
            raise serializers.ValidationError(
                "Votre compte n'est rattaché à aucune filiale : impossible d'enregistrer une visite."
            )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        utilisateur = request.user if request else None
        validated_data["filiale"] = utilisateur.filiale
        validated_data["enregistre_par"] = utilisateur

        visite = Visite.objects.create(**validated_data)
        self._notifier_secretariat(visite)
        return visite

    def _notifier_secretariat(self, visite):
        """Signale la nouvelle demande aux secrétaires de la filiale, même schéma que RG-02 côté réservations."""
        from django.contrib.auth import get_user_model
        from applications.notifications.services import envoyer_notification

        User = get_user_model()
        secretaires = User.objects.filter(filiale=visite.filiale_id, role=User.Role.SECRETAIRE)
        for secretaire in secretaires:
            envoyer_notification(
                secretaire,
                "Visiteur à l'accueil",
                f"{visite.prenom} {visite.nom} — {visite.motif}",
                "INFO",
                objet=visite,
            )
