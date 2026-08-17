from django.db import models


class Filiale(models.Model):
    """
    Représente une société ou entité du groupe.

    Exemples :
    - OSEOR
    - KAPI
    - BONICI
    """

    nom = models.CharField(
        verbose_name="Nom",
        max_length=150,
        unique=True
    )

    code = models.CharField(
        verbose_name="Code",
        max_length=20,
        unique=True
    )

    description = models.TextField(
        verbose_name="Description",
        blank=True
    )

    email = models.EmailField(
        verbose_name="Email",
        blank=True
    )

    telephone = models.CharField(
        verbose_name="Téléphone",
        max_length=30,
        blank=True
    )

    adresse = models.TextField(
        verbose_name="Adresse",
        blank=True
    )

    active = models.BooleanField(
        verbose_name="Filiale active",
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
        verbose_name = "Filiale"
        verbose_name_plural = "Filiales"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class ParametreFiliale(models.Model):
    """
    Paramètres métier de réservation propres à chaque filiale.
    """

    filiale = models.OneToOneField(
        Filiale,
        on_delete=models.CASCADE,
        related_name="parametres",
        verbose_name="Filiale"
    )

    delai_min_reservation = models.PositiveIntegerField(
        verbose_name="Délai minimum avant réservation (minutes)",
        default=30
    )

    duree_max_reservation = models.PositiveIntegerField(
        verbose_name="Durée maximale d'une réservation (minutes)",
        default=480
    )

    nb_max_reservations_actives = models.PositiveIntegerField(
        verbose_name="Nombre maximum de réservations simultanées",
        default=5
    )

    delai_annulation = models.PositiveIntegerField(
        verbose_name="Délai d'annulation avant début (minutes)",
        default=60
    )

    class Meta:
        verbose_name = "Paramètre filiale"
        verbose_name_plural = "Paramètres filiales"

    def __str__(self):
        return f"Paramètres - {self.filiale.nom}"