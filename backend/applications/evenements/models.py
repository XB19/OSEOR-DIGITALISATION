from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Evenement(models.Model):
    """
    Événement de la vie interne du groupe : cérémonie, discours, fête,
    réception, séminaire…

    Les anniversaires n'ont volontairement PAS de ligne ici : ils se
    déduisent de `Utilisateur.date_naissance` (voir `services.py`). Les
    stocker reviendrait à recréer chaque année autant de lignes que
    d'employés, et à les désynchroniser dès qu'une date de naissance est
    corrigée.
    """

    class TypeEvenement(models.TextChoices):
        CEREMONIE = "CEREMONIE", "Cérémonie"
        DISCOURS = "DISCOURS", "Discours"
        FETE = "FETE", "Fête"
        RECEPTION = "RECEPTION", "Réception"
        SEMINAIRE = "SEMINAIRE", "Séminaire / Formation"
        AUTRE = "AUTRE", "Autre"

    class Visibilite(models.TextChoices):
        GROUPE = "GROUPE", "Tout le groupe"
        FILIALE = "FILIALE", "La filiale seulement"
        SERVICE = "SERVICE", "Le service seulement"

    titre = models.CharField(
        verbose_name="Titre",
        max_length=200
    )

    type_evenement = models.CharField(
        verbose_name="Type",
        max_length=20,
        choices=TypeEvenement.choices,
        default=TypeEvenement.AUTRE
    )

    description = models.TextField(
        verbose_name="Description",
        blank=True
    )

    date_debut = models.DateTimeField(
        verbose_name="Début"
    )

    date_fin = models.DateTimeField(
        verbose_name="Fin"
    )

    journee_entiere = models.BooleanField(
        verbose_name="Journée entière",
        default=False,
        help_text="Masque les heures à l'affichage (fête, jour férié…)."
    )

    lieu = models.CharField(
        verbose_name="Lieu",
        max_length=200,
        blank=True
    )

    salle = models.ForeignKey(
        "salles.Salle",
        verbose_name="Salle",
        on_delete=models.SET_NULL,
        related_name="evenements",
        null=True,
        blank=True,
        help_text="Si l'événement se tient dans une salle du groupe."
    )

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.CASCADE,
        related_name="evenements"
    )

    service = models.ForeignKey(
        "filiales.Service",
        verbose_name="Service",
        on_delete=models.SET_NULL,
        related_name="evenements",
        null=True,
        blank=True
    )

    visibilite = models.CharField(
        verbose_name="Visibilité",
        max_length=20,
        choices=Visibilite.choices,
        default=Visibilite.FILIALE
    )

    photo = models.ImageField(
        verbose_name="Illustration",
        upload_to="evenements/",
        null=True,
        blank=True
    )

    createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.PROTECT,
        related_name="evenements_crees"
    )

    annule = models.BooleanField(
        verbose_name="Annulé",
        default=False
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
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ["date_debut"]
        indexes = [
            models.Index(fields=["date_debut"]),
            models.Index(fields=["filiale", "date_debut"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_fin__gte=models.F("date_debut")),
                name="evenement_fin_apres_debut",
            ),
        ]

    def __str__(self):
        return f"{self.titre} ({self.date_debut:%d/%m/%Y})"

    def clean(self):
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError({
                "date_fin": "La fin ne peut pas précéder le début.",
            })

        if self.visibilite == self.Visibilite.SERVICE and not self.service_id:
            raise ValidationError({
                "service": "Une visibilité « service » impose de désigner le service.",
            })

        if self.service_id and self.filiale_id:
            if self.service.filiale_id != self.filiale_id:
                raise ValidationError({
                    "service": "Le service doit appartenir à la filiale de l'événement.",
                })
