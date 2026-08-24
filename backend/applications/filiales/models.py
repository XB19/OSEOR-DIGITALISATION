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

class Service(models.Model):
    """
    Service (ou département) au sein d'une filiale : Comptabilité, Moyens
    Généraux, Informatique…

    Complète le rôle `CHEF_SERVICE` de l'utilisateur, qui indiquait jusqu'ici
    qu'une personne dirigeait « un service » sans jamais dire lequel. Le
    rattachement d'un utilisateur à un service (`Utilisateur.service`) et la
    désignation de son chef (`Service.chef`) rendent exploitables les
    validations « chef de service », le périmètre des stocks et la chaîne de
    validation des congés.
    """

    nom = models.CharField(
        verbose_name="Nom",
        max_length=150
    )

    code = models.CharField(
        verbose_name="Code",
        max_length=20
    )

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.CASCADE,
        related_name="services"
    )

    chef = models.ForeignKey(
        "utilisateurs.Utilisateur",
        verbose_name="Chef de service",
        on_delete=models.SET_NULL,
        related_name="services_diriges",
        null=True,
        blank=True,
        help_text="Responsable du service. Fait autorité pour les validations."
    )

    description = models.TextField(
        verbose_name="Description",
        blank=True
    )

    actif = models.BooleanField(
        verbose_name="Service actif",
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
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ["filiale__nom", "nom"]
        # Le code n'est unique qu'au sein d'une filiale : deux entreprises du
        # groupe peuvent chacune avoir leur service « COMPTA ».
        constraints = [
            models.UniqueConstraint(
                fields=["filiale", "code"],
                name="service_code_unique_par_filiale",
            ),
        ]

    def __str__(self):
        return f"{self.nom} ({self.filiale.code})"

    def clean(self):
        """Le chef d'un service doit appartenir à la filiale de ce service."""
        from django.core.exceptions import ValidationError

        if self.chef_id and self.filiale_id:
            if self.chef.filiale_id != self.filiale_id:
                raise ValidationError({
                    "chef": "Le chef de service doit appartenir à la même filiale "
                            "que le service.",
                })
