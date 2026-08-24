from django.conf import settings
from django.db import models
from django.utils import timezone


class Contrat(models.Model):
    """
    Registre des contrats de la filiale (fournisseur, client, prestation de
    services, bail…) : enregistrement, pièces jointes et suivi de la date
    d'échéance. Les alertes d'expiration sont gérées par
    `applications.contrats.services.verifier_echeances_et_alerter`.
    """

    class TypeContrat(models.TextChoices):
        FOURNISSEUR = "FOURNISSEUR", "Contrat fournisseur"
        CLIENT = "CLIENT", "Contrat client"
        PRESTATAIRE = "PRESTATAIRE", "Prestation de services"
        BAIL = "BAIL", "Bail / location"
        AUTRE = "AUTRE", "Autre"

    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        EXPIRE = "EXPIRE", "Expiré"
        RESILIE = "RESILIE", "Résilié"

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.PROTECT,
        related_name="contrats",
    )

    numero = models.CharField(
        verbose_name="Numéro",
        max_length=40,
        unique=True,
        editable=False,
    )

    intitule = models.CharField(
        verbose_name="Intitulé",
        max_length=200,
    )

    partie_contractante = models.CharField(
        verbose_name="Partie contractante",
        max_length=200,
        help_text="Nom du fournisseur, client ou prestataire.",
    )

    type_contrat = models.CharField(
        verbose_name="Type de contrat",
        max_length=20,
        choices=TypeContrat.choices,
    )

    reference = models.CharField(
        verbose_name="Référence",
        max_length=100,
        blank=True,
        help_text="Numéro de référence du contrat papier, si applicable.",
    )

    date_debut = models.DateField(
        verbose_name="Date de début",
    )

    date_echeance = models.DateField(
        verbose_name="Date d'échéance",
        null=True,
        blank=True,
        help_text="Laisser vide si le contrat est à durée indéterminée (aucune alerte ne sera envoyée).",
    )

    montant = models.DecimalField(
        verbose_name="Montant",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )

    description = models.TextField(
        verbose_name="Description",
        blank=True,
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=10,
        choices=Statut.choices,
        default=Statut.ACTIF,
    )

    motif_resiliation = models.TextField(
        verbose_name="Motif de résiliation",
        blank=True,
    )

    date_resiliation = models.DateField(
        verbose_name="Date de résiliation",
        null=True,
        blank=True,
    )

    seuils_alertes_envoyes = models.JSONField(
        verbose_name="Seuils d'alerte déjà notifiés",
        default=list,
        blank=True,
        help_text="Empêche l'envoi en double des alertes d'échéance (30/15/7/3/1 jours, ou EXPIRE).",
    )

    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Enregistré par",
        on_delete=models.PROTECT,
        related_name="contrats_enregistres",
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de création",
        auto_now_add=True,
    )

    date_modification = models.DateTimeField(
        verbose_name="Date de modification",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Contrat"
        verbose_name_plural = "Contrats"
        ordering = ["-date_creation"]
        indexes = [
            models.Index(fields=["filiale", "statut"]),
            models.Index(fields=["date_echeance"]),
        ]

    def __str__(self):
        return f"{self.numero} — {self.intitule}"

    @property
    def jours_avant_echeance(self):
        if not self.date_echeance:
            return None
        return (self.date_echeance - timezone.localdate()).days


class PieceJointeContrat(models.Model):
    """Pièce jointe d'un contrat (scan signé, avenant…) — plusieurs par contrat."""

    contrat = models.ForeignKey(
        Contrat,
        verbose_name="Contrat",
        on_delete=models.CASCADE,
        related_name="pieces_jointes",
    )

    fichier = models.FileField(
        verbose_name="Fichier",
        upload_to="contrats/pieces_jointes/%Y/%m/",
    )

    nom_original = models.CharField(
        verbose_name="Nom du fichier",
        max_length=255,
        blank=True,
    )

    ajoute_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Ajouté par",
        on_delete=models.PROTECT,
        related_name="pieces_jointes_contrats",
    )

    date_ajout = models.DateTimeField(
        verbose_name="Date d'ajout",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Pièce jointe de contrat"
        verbose_name_plural = "Pièces jointes de contrat"
        ordering = ["-date_ajout"]

    def __str__(self):
        return self.nom_original or self.fichier.name
