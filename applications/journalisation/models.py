from django.db import models
from django.conf import settings


class JournalAction(models.Model):
    """
    Journal d'audit (EF-20) : trace horodatée des actions sensibles
    (création/validation/refus/annulation de réservations, audiences,
    gestion des salles et des utilisateurs).
    """

    acteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="actions_journal",
        verbose_name="Acteur",
        null=True,
        blank=True
    )

    action = models.CharField(
        verbose_name="Action",
        max_length=80,
        help_text="Code de l'action, ex. RESERVATION_VALIDEE."
    )

    cible = models.CharField(
        verbose_name="Cible",
        max_length=255,
        blank=True,
        help_text="Description lisible de l'objet concerné."
    )

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

    details = models.JSONField(
        verbose_name="Détails",
        default=dict,
        blank=True
    )

    date_creation = models.DateTimeField(
        verbose_name="Horodatage",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Action journalisée"
        verbose_name_plural = "Journal des actions"
        ordering = ["-date_creation"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["objet_type", "objet_id"]),
        ]

    def __str__(self):
        return f"{self.date_creation:%d/%m/%Y %H:%M} - {self.action} ({self.acteur})"
