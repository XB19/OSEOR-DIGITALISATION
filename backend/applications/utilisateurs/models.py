import base64
import hashlib

from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from cryptography.fernet import Fernet, InvalidToken


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

        SECRETAIRE = (
            "SECRETAIRE",
            "Secrétaire / Assistante de direction"
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
    def est_secretaire(self):
        return self.role == self.Role.SECRETAIRE

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


def _cle_chiffrement() -> bytes:
    """
    Dérive une clé Fernet stable depuis SECRET_KEY, pour éviter d'avoir à
    gérer une clé de chiffrement séparée. Si SECRET_KEY change (rotation),
    les mots de passe déjà enregistrés ne seront plus déchiffrables et
    devront être ressaisis.
    """
    empreinte = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(empreinte)


class ParametreLDAP(models.Model):
    """
    Configuration de connexion à l'Active Directory local (LDAP), saisie par
    l'administrateur depuis l'application (remplace les variables .env
    LDAP_* utilisées auparavant). Table à une seule ligne (singleton).
    """

    server_uri = models.CharField(
        verbose_name="Adresse du serveur LDAP",
        max_length=255,
        blank=True,
        help_text="Ex. ldap://192.168.1.10 (ou ldaps:// pour le chiffrement TLS).",
    )

    domaine = models.CharField(
        verbose_name="Domaine NetBIOS",
        max_length=100,
        blank=True,
        help_text="Nom NetBIOS du domaine Windows, ex. OSEOR.",
    )

    base_dn = models.CharField(
        verbose_name="Base DN",
        max_length=255,
        blank=True,
        help_text="Ex. DC=oseor,DC=local",
    )

    bind_dn = models.CharField(
        verbose_name="DN du compte de service",
        max_length=255,
        blank=True,
        help_text="Ex. CN=svcOseor,OU=Services,DC=oseor,DC=local",
    )

    bind_password_chiffre = models.TextField(
        verbose_name="Mot de passe du compte de service (chiffré)",
        blank=True,
    )

    date_modification = models.DateTimeField(
        verbose_name="Dernière modification",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Paramètre LDAP"
        verbose_name_plural = "Paramètres LDAP"

    def __str__(self):
        return "Configuration Active Directory (LDAP)"

    def save(self, *args, **kwargs):
        # Ligne unique : toujours pk=1.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def charger(cls) -> "ParametreLDAP":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def configure(self) -> bool:
        return bool(self.server_uri and self.domaine and self.base_dn and self.bind_dn)

    @property
    def bind_password(self) -> str:
        if not self.bind_password_chiffre:
            return ""
        try:
            return Fernet(_cle_chiffrement()).decrypt(self.bind_password_chiffre.encode()).decode()
        except InvalidToken:
            return ""

    @bind_password.setter
    def bind_password(self, valeur: str):
        if valeur:
            self.bind_password_chiffre = Fernet(_cle_chiffrement()).encrypt(valeur.encode()).decode()