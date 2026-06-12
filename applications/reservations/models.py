from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from applications.salles.models import Salle


class Reservation(models.Model):
    """
    Demande de réservation d'une salle.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        CONFIRMEE = "CONFIRMEE", "Confirmée"
        REFUSEE = "REFUSEE", "Refusée"
        ANNULEE = "ANNULEE", "Annulée"
        TERMINEE = "TERMINEE", "Terminée"

    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="Demandeur"
    )

    nom_reservant = models.CharField(
        verbose_name="Nom du réservant",
        max_length=255
    )

    salle = models.ForeignKey(
        Salle,
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="Salle"
    )

    date_reunion = models.DateField(
        verbose_name="Date de réunion"
    )

    heure_debut = models.TimeField(
        verbose_name="Heure de début"
    )

    heure_fin = models.TimeField(
        verbose_name="Heure de fin"
    )

    precisions = models.TextField(
        verbose_name="Précisions spécifiques",
        blank=True,
        help_text=(
            "Café, boissons, collations, "
            "matériel supplémentaire, etc."
        )
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE
    )

    motif_refus = models.TextField(
        verbose_name="Motif du refus",
        blank=True
    )

    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations_validees",
        verbose_name="Validée par",
        null=True,
        blank=True
    )

    date_validation = models.DateTimeField(
        verbose_name="Date de validation",
        null=True,
        blank=True
    )

    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations_annulees",
        verbose_name="Annulée par",
        null=True,
        blank=True
    )

    date_annulation = models.DateTimeField(
        verbose_name="Date d'annulation",
        null=True,
        blank=True
    )

    motif_annulation = models.TextField(
        verbose_name="Motif d'annulation",
        blank=True
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de création",
        auto_now_add=True
    )

    date_modification = models.DateTimeField(
        verbose_name="Date de modification",
        auto_now=True
    )

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = [
            "-date_reunion",
            "-heure_debut"
        ]

        indexes = [
            models.Index(
                fields=[
                    "salle",
                    "date_reunion"
                ]
            )
        ]

    def clean(self):
        """
        Vérification des règles métier.
        """

        if self.heure_debut >= self.heure_fin:
            raise ValidationError(
                "L'heure de fin doit être supérieure à l'heure de début."
            )

        reservations_conflit = Reservation.objects.filter(
            salle=self.salle,
            date_reunion=self.date_reunion,
            statut__in=[
                self.Statut.EN_ATTENTE,
                self.Statut.CONFIRMEE
            ]
        )

        if self.pk:
            reservations_conflit = reservations_conflit.exclude(
                pk=self.pk
            )

        for reservation in reservations_conflit:

            if (
                self.heure_debut < reservation.heure_fin
                and
                self.heure_fin > reservation.heure_debut
            ):
                raise ValidationError(
                    "Cette salle est déjà réservée sur ce créneau."
                )

    def save(self, *args, **kwargs):
        """
        Validation automatique avant sauvegarde.
        """

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.nom_reservant} - "
            f"{self.salle.nom} - "
            f"{self.date_reunion}"
        )


class Participant(models.Model):
    """
    Personne invitée à la réunion.
    """

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Réservation"
    )

    nom_complet = models.CharField(
        verbose_name="Nom complet",
        max_length=255
    )

    email = models.EmailField(
        verbose_name="Email",
        blank=True
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de création",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Participant"
        verbose_name_plural = "Participants"
        ordering = ["nom_complet"]

    def __str__(self):
        return self.nom_complet