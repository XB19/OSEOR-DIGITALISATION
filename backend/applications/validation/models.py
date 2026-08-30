from django.conf import settings
from django.db import models


class DecisionValidation(models.Model):
    """
    Trace d'une décision prise dans un circuit de validation.

    Générique — rattachée à n'importe quel objet par (`objet_type`,
    `objet_id`), comme le journal d'audit et les notifications. Le module
    métier garde son propre statut ; c'est ici que se conserve le détail de
    QUI a décidé QUOI, à QUELLE étape.

    Jamais modifiée : une décision se corrige en en ajoutant une autre.
    Une validation directe consigne les étapes qu'elle a sautées — un
    contournement dont il ne resterait pas trace serait la première chose
    qu'un auditeur reprocherait.
    """

    class Sens(models.TextChoices):
        VALIDEE = "VALIDEE", "Validée"
        REFUSEE = "REFUSEE", "Refusée"

    objet_type = models.CharField(
        verbose_name="Type d'objet",
        max_length=100
    )

    objet_id = models.PositiveIntegerField(
        verbose_name="Identifiant de l'objet"
    )

    etape_cle = models.CharField(
        verbose_name="Clé de l'étape",
        max_length=60
    )

    etape_libelle = models.CharField(
        verbose_name="Étape",
        max_length=150
    )

    ordre = models.PositiveSmallIntegerField(
        verbose_name="Rang de l'étape",
        default=0
    )

    acteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Décidé par",
        on_delete=models.PROTECT,
        related_name="decisions_validation"
    )

    sens = models.CharField(
        verbose_name="Sens",
        max_length=10,
        choices=Sens.choices
    )

    validation_directe = models.BooleanField(
        verbose_name="Validation directe",
        default=False,
        help_text="Décision prise par une autorité supérieure sans attendre "
                  "les étapes précédentes."
    )

    etapes_sautees = models.JSONField(
        verbose_name="Étapes court-circuitées",
        default=list,
        blank=True
    )

    commentaire = models.TextField(
        verbose_name="Commentaire",
        blank=True
    )

    date_decision = models.DateTimeField(
        verbose_name="Date de la décision",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Décision de validation"
        verbose_name_plural = "Décisions de validation"
        ordering = ["objet_type", "objet_id", "ordre", "date_decision"]
        indexes = [
            models.Index(fields=["objet_type", "objet_id"]),
            models.Index(fields=["acteur", "-date_decision"]),
        ]

    def __str__(self):
        marque = " (validation directe)" if self.validation_directe else ""
        return (f"{self.objet_type}#{self.objet_id} — {self.etape_libelle} : "
                f"{self.get_sens_display()}{marque}")
