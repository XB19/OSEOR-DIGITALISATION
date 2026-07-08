from django.db import models

from applications.filiales.models import Filiale


class Salle(models.Model):
    """
    Salle de réunion ou de collaboration.
    """

    class Equipement(models.TextChoices):
        VIDEO_PROJECTEUR = (
            "VIDEO_PROJECTEUR",
            "Vidéoprojecteur"
        )

        TABLEAU_BLANC = (
            "TABLEAU_BLANC",
            "Tableau blanc"
        )

        POINTEUR_LASER = (
            "POINTEUR_LASER",
            "Pointeur laser"
        )

    nom = models.CharField(
        verbose_name="Nom de la salle",
        max_length=150
    )

    filiale = models.ForeignKey(
        Filiale,
        verbose_name="Filiale propriétaire",
        on_delete=models.PROTECT,
        related_name="salles",
        help_text="Filiale qui possède et gère la salle. "
                  "Ses réservations sont validées par le secrétariat de cette filiale."
    )

    description = models.TextField(
        verbose_name="Description",
        blank=True
    )

    capacite = models.PositiveIntegerField(
        verbose_name="Capacité d'accueil"
    )

    equipements = models.JSONField(
        verbose_name="Équipements disponibles",
        default=list,
        blank=True
    )

    photo = models.ImageField(
        verbose_name="Photo de la salle",
        upload_to="salles/photos/",
        null=True,
        blank=True
    )

    active = models.BooleanField(
        verbose_name="Salle active",
        default=True
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
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.filiale.nom})"