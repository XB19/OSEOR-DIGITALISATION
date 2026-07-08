from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Reservation, Participant, SerieRecurrence


class ParticipantSerializer(serializers.ModelSerializer):
    nom_complet = serializers.CharField(read_only=True)

    class Meta:
        model = Participant
        fields = (
            "id",
            "nom",
            "prenom",
            "nom_complet",
            "email",
            "telephone",
            "societe",
            "type_participant",
            "utilisateur",
        )


class ReservationSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True, required=False)
    # Renseignés automatiquement depuis l'utilisateur connecté si absents.
    demandeur = serializers.PrimaryKeyRelatedField(
        queryset=Reservation._meta.get_field("demandeur").related_model.objects.all(),
        required=False,
    )
    nom_reservant = serializers.CharField(required=False, allow_blank=True)
    salle_nom = serializers.CharField(source="salle.nom", read_only=True)
    filiale_nom = serializers.CharField(source="salle.filiale.nom", read_only=True)
    demandeur_nom = serializers.CharField(source="demandeur.nom_complet", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    # Infos de la série récurrente (badge « Récurrente » côté frontend)
    serie_frequence = serializers.CharField(
        source="serie.get_frequence_display", read_only=True, default=None)
    serie_date_debut = serializers.DateField(
        source="serie.date_debut", read_only=True, default=None)
    serie_date_fin = serializers.DateField(
        source="serie.date_fin", read_only=True, default=None)

    class Meta:
        model = Reservation
        fields = (
            "id",
            "demandeur",
            "demandeur_nom",
            "nom_reservant",
            "telephone",
            "motif",
            "salle",
            "salle_nom",
            "filiale_nom",
            "date_reunion",
            "heure_debut",
            "heure_fin",
            "precisions",
            "statut",
            "statut_libelle",
            "motif_refus",
            "motif_annulation",
            "valide_par",
            "date_validation",
            "serie",
            "serie_frequence",
            "serie_date_debut",
            "serie_date_fin",
            "participants",
            "date_creation",
        )
        read_only_fields = (
            "statut",
            "motif_refus",
            "motif_annulation",
            "valide_par",
            "date_validation",
            "serie",
            "date_creation",
        )

    def _creer_participants(self, reservation, participants_data):
        for p in participants_data:
            Participant.objects.create(reservation=reservation, **p)

    def create(self, validated_data):
        participants_data = validated_data.pop("participants", [])
        request = self.context.get("request")
        user = request.user if request else None

        if user and not validated_data.get("demandeur"):
            validated_data["demandeur"] = user
        if user and not validated_data.get("nom_reservant"):
            validated_data["nom_reservant"] = user.nom_complet

        # Secrétaire et Administrateur : validation immédiate, pas de circuit d'approbation.
        est_gestionnaire = user and user.role in ("SECRETAIRE", "ADMINISTRATEUR")
        if est_gestionnaire:
            from django.utils import timezone
            validated_data["statut"] = Reservation.Statut.VALIDEE
            validated_data["valide_par"] = user
            validated_data["date_validation"] = timezone.now()

        reservation = Reservation(**validated_data)
        try:
            reservation.save()
        except DjangoValidationError as e:
            raise serializers.ValidationError({"non_field_errors": e.messages})

        self._creer_participants(reservation, participants_data)
        if not est_gestionnaire:
            # Notifie le secrétariat uniquement si c'est un employé/autre qui demande
            self._notifier_secretariat(reservation)
        self._convoquer_participants(reservation)
        return reservation

    def _convoquer_participants(self, reservation):
        """
        RG-13 : convoque automatiquement les participants internes
        (liés à un compte utilisateur, ou retrouvés par e-mail).
        """
        from django.contrib.auth import get_user_model
        from applications.notifications.services import envoyer_notification

        User = get_user_model()
        creneau = (f"{reservation.date_reunion} de "
                   f"{reservation.heure_debut:%H:%M} à {reservation.heure_fin:%H:%M}")
        deja = set()
        for p in reservation.participants.all():
            if p.type_participant != Participant.Type.INTERNE:
                continue
            user = None
            if p.utilisateur_id:
                user = p.utilisateur
            elif p.email:
                user = User.objects.filter(email__iexact=p.email).first()
            if not user or user.id in deja or user.id == reservation.demandeur_id:
                continue
            deja.add(user.id)
            envoyer_notification(
                user,
                "Invitation à une réunion",
                f"Vous êtes convié(e) à une réunion"
                f"{' — ' + reservation.motif if reservation.motif else ''} "
                f"en salle {reservation.salle.nom}, le {creneau}.",
                "INFO",
            )

    def _notifier_secretariat(self, reservation):
        """RG-02 : notifie les secrétaires de la filiale propriétaire de la salle."""
        from django.contrib.auth import get_user_model
        from applications.notifications.services import envoyer_notification

        User = get_user_model()
        secretaires = User.objects.filter(
            filiale=reservation.salle.filiale_id,
            role=User.Role.SECRETAIRE,
        )
        for secretaire in secretaires:
            envoyer_notification(
                secretaire,
                "Nouvelle demande de réservation",
                f"{reservation.nom_reservant} — salle {reservation.salle.nom} "
                f"le {reservation.date_reunion} ({reservation.heure_debut:%H:%M}"
                f"-{reservation.heure_fin:%H:%M})",
                "INFO",
            )

    def update(self, instance, validated_data):
        participants_data = validated_data.pop("participants", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.save()
        except DjangoValidationError as e:
            raise serializers.ValidationError({"non_field_errors": e.messages})
        if participants_data is not None:
            instance.participants.all().delete()
            self._creer_participants(instance, participants_data)
        return instance


class SerieRecurrenceSerializer(serializers.ModelSerializer):
    salle_nom = serializers.CharField(source="salle.nom", read_only=True)
    nb_occurrences = serializers.SerializerMethodField()

    class Meta:
        model = SerieRecurrence
        fields = (
            "id",
            "demandeur",
            "nom_reservant",
            "telephone",
            "motif",
            "salle",
            "salle_nom",
            "frequence",
            "jours_semaine",
            "heure_debut",
            "heure_fin",
            "date_debut",
            "date_fin",
            "precisions",
            "nb_occurrences",
        )
        read_only_fields = ("demandeur",)

    def get_nb_occurrences(self, obj):
        return obj.occurrences.count()

    def validate(self, attrs):
        if attrs["heure_debut"] >= attrs["heure_fin"]:
            raise serializers.ValidationError(
                "L'heure de fin doit être postérieure à l'heure de début."
            )
        if attrs["date_debut"] > attrs["date_fin"]:
            raise serializers.ValidationError(
                "La date de fin doit être postérieure à la date de début."
            )
        if attrs["date_debut"] == attrs["date_fin"]:
            raise serializers.ValidationError(
                "Une réservation récurrente doit couvrir plus d'un jour. "
                "Pour une seule date, utilisez le formulaire de réservation simple."
            )
        return attrs
