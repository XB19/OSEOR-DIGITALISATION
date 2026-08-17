from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    Notification système envoyée à un utilisateur.
    """

    class TypeNotification(models.TextChoices):
        INFO = "INFO", "Information"
        SUCCESS = "SUCCESS", "Succès"
        WARNING = "WARNING", "Avertissement"
        ERROR = "ERROR", "Erreur"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Utilisateur"
    )

    titre = models.CharField(
        verbose_name="Titre",
        max_length=255
    )

    message = models.TextField(
        verbose_name="Message"
    )

    type = models.CharField(
        verbose_name="Type",
        max_length=20,
        choices=TypeNotification.choices,
        default=TypeNotification.INFO
    )

    lu = models.BooleanField(
        verbose_name="Lu",
        default=False
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de création",
        auto_now_add=True
    )

    date_lecture = models.DateTimeField(
        verbose_name="Date de lecture",
        null=True,
        blank=True
    )

    # Lien générique vers l'objet concerné (ex. Reservation, Audience,
    # Document), pour permettre au clic sur la notification d'ouvrir
    # directement l'élément à traiter. Même pattern que JournalAction.
    objet_type = models.CharField(
        verbose_name="Type d'objet",
        max_length=60,
        blank=True
    )

    objet_id = models.PositiveIntegerField(
        verbose_name="Identifiant de l'objet",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.titre} - {self.utilisateur}"