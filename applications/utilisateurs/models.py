from django.db import models
from django.contrib.auth.models import AbstractUser


class Utilisateur(AbstractUser):
    """
    Utilisateur principal de la plateforme OSEOR DIGITALISATION.

    Utilisé pour :
    - Authentification Web
    - Authentification Mobile Flutter
    - Workflows de validation
    - Signature électronique
    - Gestion documentaire
    - Gestion des salles
    - Gestion des déplacements
    """

    class Role(models.TextChoices):

        ADMINISTRATEUR = (
            "ADMINISTRATEUR",
            "Administrateur Groupe"
        )

        DIRECTEUR = (
            "DIRECTEUR",
            "Directeur"
        )

        CHEF_SERVICE = (
            "CHEF_SERVICE",
            "Chef de service"
        )

        COMPTABLE = (
            "COMPTABLE",
            "Comptable"
        )

        RH = (
            "RH",
            "Ressources Humaines"
        )

        EMPLOYE = (
            "EMPLOYE",
            "Employé"
        )

    role = models.CharField(
        verbose_name="Rôle",
        max_length=30,
        choices=Role.choices,
        default=Role.EMPLOYE
    )

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.PROTECT,
        related_name="utilisateurs",
        null=True,
        blank=True
    )

    telephone = models.CharField(
        verbose_name="Téléphone",
        max_length=30,
        blank=True
    )

    photo_profil = models.ImageField(
        verbose_name="Photo de profil",
        upload_to="utilisateurs/photos/",
        null=True,
        blank=True
    )

    signature = models.ImageField(
        verbose_name="Signature électronique",
        upload_to="utilisateurs/signatures/",
        null=True,
        blank=True,
        help_text="Signature utilisée lors des validations."
    )

    actif = models.BooleanField(
        verbose_name="Compte actif",
        default=True
    )

    derniere_connexion_mobile = models.DateTimeField(
        verbose_name="Dernière connexion mobile",
        null=True,
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
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = [
            "last_name",
            "first_name"
        ]

    def __str__(self):
        return self.nom_complet

    @property
    def nom_complet(self):
        nom = self.get_full_name()

        if nom:
            return nom

        return self.username

    @property
    def est_administrateur(self):
        return self.role == self.Role.ADMINISTRATEUR

    @property
    def est_directeur(self):
        return self.role == self.Role.DIRECTEUR

    @property
    def est_chef_service(self):
        return self.role == self.Role.CHEF_SERVICE

    @property
    def est_comptable(self):
        return self.role == self.Role.COMPTABLE

    @property
    def est_rh(self):
        return self.role == self.Role.RH

    @property
    def est_employe(self):
        return self.role == self.Role.EMPLOYE