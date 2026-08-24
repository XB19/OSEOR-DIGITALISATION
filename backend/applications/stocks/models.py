from django.conf import settings
from django.db import models


class Article(models.Model):
    """
    Un article de stock (matériel, matériel informatique, fournitures de
    bureau…) suivi par filiale. `quantite_stock` n'est jamais modifiable
    directement : elle ne change qu'au travers de MouvementStock, pour
    garder une traçabilité complète des entrées/sorties (comme un registre).
    """

    class Categorie(models.TextChoices):
        MATERIEL = "MATERIEL", "Matériel"
        INFORMATIQUE = "INFORMATIQUE", "Matériel informatique"
        FOURNITURES = "FOURNITURES", "Fournitures de bureau"

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.PROTECT,
        related_name="articles",
    )

    nom = models.CharField(
        verbose_name="Nom",
        max_length=150,
    )

    categorie = models.CharField(
        verbose_name="Catégorie",
        max_length=20,
        choices=Categorie.choices,
    )

    unite = models.CharField(
        verbose_name="Unité",
        max_length=30,
        default="unité",
        help_text="Ex. pièce, ramette, boîte…",
    )

    quantite_stock = models.PositiveIntegerField(
        verbose_name="Quantité en stock",
        default=0,
        editable=False,
    )

    seuil_alerte = models.PositiveIntegerField(
        verbose_name="Seuil d'alerte",
        default=0,
        help_text="Une notification est envoyée quand le stock descend à ce niveau ou en dessous.",
    )

    description = models.TextField(
        verbose_name="Description",
        blank=True,
    )

    actif = models.BooleanField(
        verbose_name="Actif",
        default=True,
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
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["filiale", "categorie"]),
        ]

    def __str__(self):
        return f"{self.nom} ({self.filiale.code})"

    @property
    def en_alerte(self) -> bool:
        return self.quantite_stock <= self.seuil_alerte


class MouvementStock(models.Model):
    """
    Entrée ou sortie de stock — registre append-only (jamais modifié ni
    supprimé après coup), comme l'historique des visas des documents.
    """

    class Type(models.TextChoices):
        ENTREE = "ENTREE", "Entrée"
        SORTIE = "SORTIE", "Sortie"

    article = models.ForeignKey(
        Article,
        verbose_name="Article",
        on_delete=models.PROTECT,
        related_name="mouvements",
    )

    type_mouvement = models.CharField(
        verbose_name="Type",
        max_length=10,
        choices=Type.choices,
    )

    quantite = models.PositiveIntegerField(
        verbose_name="Quantité",
    )

    motif = models.CharField(
        verbose_name="Motif",
        max_length=255,
        blank=True,
        help_text="Ex. « Achat fournisseur X », « Attribution à Y »…",
    )

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Utilisateur",
        on_delete=models.PROTECT,
        related_name="mouvements_stock",
    )

    date_creation = models.DateTimeField(
        verbose_name="Date",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.get_type_mouvement_display()} {self.quantite} — {self.article.nom}"
