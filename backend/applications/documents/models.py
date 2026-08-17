from django.db import models
from django.conf import settings


class TypeDocument(models.TextChoices):
    """
    Documents administratifs (« Moyens Généraux »), au-delà de la
    réservation de salles et des audiences.
    """

    FICHE_BESOIN = "FICHE_BESOIN", "Fiche de besoin"
    DEMANDE_ACHAT = "DEMANDE_ACHAT", "Demande d'achat"
    FICHE_TRANSPORT = "FICHE_TRANSPORT", "Fiche de transport"
    BON_SORTIE_CAISSE = "BON_SORTIE_CAISSE", "Bon de sortie de caisse"


class ConfigurationDocument(models.Model):
    """
    Configuration d'un type de document pour une filiale donnée : chaque
    entreprise du groupe utilise sa propre fiche papier, avec des libellés
    de colonnes et une chaîne de visas (signatures) qui lui sont propres.
    Modifiable depuis l'admin, sans toucher au code, quand une entreprise
    change ses règles ou qu'une nouvelle filiale rejoint le groupe.

    - colonnes : liste ordonnée des colonnes du tableau de lignes, ex.
        [{"cle": "motif", "libelle": "Besoin et motifs"},
         {"cle": "beneficiaire", "libelle": "Bénéficiaire"},
         {"cle": "quantite", "libelle": "Quantité"}]
    - visas : liste ordonnée des étapes de validation, ex.
        [{"cle": "demandeur", "libelle": "Visa du Demandeur"},
         {"cle": "chef_comptable", "libelle": "Visa du Chef Comptable", "role": "COMPTABLE"},
         {"cle": "directeur_general", "libelle": "Visa du Directeur Général", "role": "DIRECTEUR"}]
      `role` (optionnel) associe l'étape à un rôle OSEOR : seul un
      utilisateur de ce rôle (ou le Directeur/Administrateur, qui peuvent
      toujours approuver/décliner/observer) peut viser cette étape.
    """

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.CASCADE,
        related_name="configurations_document",
    )

    type_document = models.CharField(
        verbose_name="Type de document",
        max_length=30,
        choices=TypeDocument.choices,
    )

    colonnes = models.JSONField(
        verbose_name="Colonnes du tableau de lignes",
        default=list,
    )

    visas = models.JSONField(
        verbose_name="Chaîne de visas (signatures)",
        default=list,
    )

    class Meta:
        verbose_name = "Configuration de document"
        verbose_name_plural = "Configurations de documents"
        unique_together = ("filiale", "type_document")

    def __str__(self):
        return f"{self.filiale.nom} — {self.get_type_document_display()}"


class Document(models.Model):
    """
    Un document administratif soumis par un utilisateur (fiche de besoin,
    demande d'achat, fiche de transport, bon de sortie de caisse…), suivant
    la configuration (colonnes + visas) de sa filiale.
    """

    class Statut(models.TextChoices):
        EN_COURS = "EN_COURS", "En cours de validation"
        VALIDE = "VALIDE", "Validé"
        REFUSE = "REFUSE", "Refusé"

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.PROTECT,
        related_name="documents",
    )

    type_document = models.CharField(
        verbose_name="Type de document",
        max_length=30,
        choices=TypeDocument.choices,
    )

    numero = models.CharField(
        verbose_name="Numéro",
        max_length=40,
        unique=True,
        editable=False,
    )

    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Demandeur",
        on_delete=models.PROTECT,
        related_name="documents",
    )

    champs_entete = models.JSONField(
        verbose_name="Champs d'en-tête",
        default=dict,
        blank=True,
        help_text="Champs spécifiques au type de document (ex. fournisseur, département…).",
    )

    lignes = models.JSONField(
        verbose_name="Lignes",
        default=list,
        blank=True,
    )

    montant_total = models.DecimalField(
        verbose_name="Montant total",
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_COURS,
    )

    etape_visa_courante = models.PositiveIntegerField(
        verbose_name="Étape de visa courante",
        default=0,
    )

    historique_visas = models.JSONField(
        verbose_name="Historique des visas",
        default=list,
        blank=True,
    )

    motif_rejet = models.TextField(
        verbose_name="Motif de rejet",
        blank=True,
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
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ["-date_creation"]
        indexes = [
            models.Index(fields=["filiale", "type_document"]),
            models.Index(fields=["statut"]),
        ]

    def __str__(self):
        return f"{self.numero} — {self.get_type_document_display()}"

    def configuration(self):
        return ConfigurationDocument.objects.filter(
            filiale=self.filiale, type_document=self.type_document,
        ).first()
