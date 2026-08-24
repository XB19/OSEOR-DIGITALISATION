from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Prestation(models.Model):
    """
    Prestation de service rendue à un client, suivie par le service qui la
    réalise.

    Le périmètre est le **service** et non la seule filiale : c'est le chef
    de service qui pilote ses prestations, et l'organigramme (étape 1) dit
    enfin lequel. L'avancement se lit à travers les jalons plutôt que par
    un pourcentage saisi à la main, qui ne veut rien dire dès qu'on ne le
    met plus à jour.
    """

    class Statut(models.TextChoices):
        PLANIFIEE = "PLANIFIEE", "Planifiée"
        EN_COURS = "EN_COURS", "En cours"
        SUSPENDUE = "SUSPENDUE", "Suspendue"
        TERMINEE = "TERMINEE", "Terminée"
        ANNULEE = "ANNULEE", "Annulée"

    reference = models.CharField(
        verbose_name="Référence",
        max_length=40,
        unique=True,
        editable=False
    )

    intitule = models.CharField(
        verbose_name="Intitulé",
        max_length=200
    )

    client = models.CharField(
        verbose_name="Client",
        max_length=200
    )

    description = models.TextField(
        verbose_name="Description",
        blank=True
    )

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.PROTECT,
        related_name="prestations"
    )

    service = models.ForeignKey(
        "filiales.Service",
        verbose_name="Service réalisateur",
        on_delete=models.PROTECT,
        related_name="prestations"
    )

    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Responsable",
        on_delete=models.PROTECT,
        related_name="prestations_dirigees"
    )

    intervenants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="Intervenants",
        related_name="prestations",
        blank=True
    )

    date_debut = models.DateField(
        verbose_name="Début"
    )

    date_fin_prevue = models.DateField(
        verbose_name="Fin prévue"
    )

    date_fin_reelle = models.DateField(
        verbose_name="Fin réelle",
        null=True,
        blank=True
    )

    montant = models.DecimalField(
        verbose_name="Montant",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0")
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.PLANIFIEE
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
        verbose_name = "Prestation de service"
        verbose_name_plural = "Prestations de services"
        ordering = ["-date_debut"]
        indexes = [
            models.Index(fields=["service", "statut"]),
            models.Index(fields=["filiale", "date_debut"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_fin_prevue__gte=models.F("date_debut")),
                name="prestation_fin_prevue_apres_debut",
            ),
            models.CheckConstraint(
                condition=models.Q(montant__gte=0),
                name="prestation_montant_positif",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.intitule}"

    @property
    def est_close(self):
        return self.statut in (self.Statut.TERMINEE, self.Statut.ANNULEE)

    @property
    def en_retard(self):
        """
        Prestation non close dont la fin prévue est dépassée.

        Se calcule, ne se stocke pas : un drapeau « en retard » enregistré
        en base est faux dès le lendemain.
        """
        from datetime import date

        if self.est_close:
            return False
        return self.date_fin_prevue < date.today()

    def clean(self):
        if self.date_debut and self.date_fin_prevue:
            if self.date_fin_prevue < self.date_debut:
                raise ValidationError({
                    "date_fin_prevue": "La fin prévue ne peut pas précéder le début.",
                })

        if self.date_fin_reelle and self.date_debut:
            if self.date_fin_reelle < self.date_debut:
                raise ValidationError({
                    "date_fin_reelle": "La fin réelle ne peut pas précéder le début.",
                })

        if self.service_id and self.filiale_id:
            if self.service.filiale_id != self.filiale_id:
                raise ValidationError({
                    "service": "Le service doit appartenir à la filiale de la "
                               "prestation.",
                })


class JalonPrestation(models.Model):
    """
    Étape d'une prestation : c'est ce qui donne l'avancement réel, sans
    demander à personne d'estimer un pourcentage.
    """

    prestation = models.ForeignKey(
        "prestations.Prestation",
        verbose_name="Prestation",
        on_delete=models.CASCADE,
        related_name="jalons"
    )

    intitule = models.CharField(
        verbose_name="Intitulé",
        max_length=200
    )

    date_prevue = models.DateField(
        verbose_name="Date prévue"
    )

    date_realisation = models.DateField(
        verbose_name="Date de réalisation",
        null=True,
        blank=True
    )

    commentaire = models.TextField(
        verbose_name="Commentaire",
        blank=True
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de création",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Jalon de prestation"
        verbose_name_plural = "Jalons de prestation"
        ordering = ["date_prevue"]

    def __str__(self):
        etat = "réalisé" if self.date_realisation else "à venir"
        return f"{self.intitule} ({etat})"

    @property
    def realise(self):
        return self.date_realisation is not None
