"""
Caisses et bons de sortie.

**Le solde d'une caisse n'est jamais un compteur.** C'est la somme de ses
mouvements, comme le solde de congés et comme le stock. Un compteur modifié
en place dérive au premier incident et devient impossible à justifier
devant un contrôle — or ici il s'agit d'argent liquide.

Trois règles viennent du terrain :

- **une alimentation exige une preuve** (chèque, reçu, référence de
  virement) : on ne fait pas grossir une caisse sur parole ;
- **le transport se paie sans validation préalable** — une course en taxi
  ne s'arbitre pas — mais une course Gozem exige son justificatif, puisque
  l'application en conserve l'historique ;
- **toute autre sortie est adressée à quelqu'un**, qui doit l'autoriser
  avant que l'argent ne sorte. Le destinataire n'est pas celui qui paie :
  l'argent vient de la caisse, lui ne fait qu'autoriser.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum


class Caisse(models.Model):
    """
    Une caisse physique, tenue par une personne dans une filiale.

    Le groupe peut en compter plusieurs — une par site, par service ou par
    usage. Le détenteur est nommé sur la caisse plutôt que par un rôle
    global : c'est cette caisse-ci qu'il tient, pas toutes.
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
        on_delete=models.PROTECT,
        related_name="caisses"
    )

    detenteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Détenteur",
        on_delete=models.SET_NULL,
        related_name="caisses_tenues",
        null=True,
        blank=True,
        help_text="Responsable de cette caisse : lui seul l'alimente et la "
                  "décaisse, avec la direction."
    )

    description = models.TextField(
        verbose_name="Description",
        blank=True
    )

    active = models.BooleanField(
        verbose_name="Caisse active",
        default=True
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de création",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Caisse"
        verbose_name_plural = "Caisses"
        ordering = ["filiale__nom", "nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["filiale", "code"],
                name="caisse_code_unique_par_filiale",
            ),
        ]

    def __str__(self):
        return f"{self.nom} ({self.filiale.code})"

    @property
    def solde(self):
        """Somme des mouvements. Jamais un champ stocké."""
        total = self.mouvements.aggregate(total=Sum("montant"))["total"]
        return total or Decimal("0")


class MouvementCaisse(models.Model):
    """
    Écriture au registre d'une caisse, jamais modifiée.

    `montant` est signé : positif pour une entrée, négatif pour une sortie.
    Une correction s'écrit en ajoutant une écriture inverse, comme en
    comptabilité.
    """

    class TypeMouvement(models.TextChoices):
        ALIMENTATION = "ALIMENTATION", "Alimentation"
        SORTIE = "SORTIE", "Sortie de caisse"
        RETOUR = "RETOUR", "Retour en caisse"
        CORRECTION = "CORRECTION", "Correction"

    #: Types qui font entrer de l'argent.
    TYPES_ENTREE = (TypeMouvement.ALIMENTATION, TypeMouvement.RETOUR)

    caisse = models.ForeignKey(
        "caisse.Caisse",
        verbose_name="Caisse",
        on_delete=models.PROTECT,
        related_name="mouvements"
    )

    type_mouvement = models.CharField(
        verbose_name="Type",
        max_length=20,
        choices=TypeMouvement.choices
    )

    montant = models.DecimalField(
        verbose_name="Montant",
        max_digits=14,
        decimal_places=2,
        help_text="Positif pour une entrée, négatif pour une sortie."
    )

    justificatif = models.FileField(
        verbose_name="Justificatif",
        upload_to="caisse/justificatifs/",
        null=True,
        blank=True,
        help_text="Chèque, reçu, capture de transaction."
    )

    reference = models.CharField(
        verbose_name="Référence",
        max_length=100,
        blank=True,
        help_text="Numéro de chèque, référence de virement…"
    )

    motif = models.CharField(
        verbose_name="Motif",
        max_length=255,
        blank=True
    )

    bon_sortie = models.ForeignKey(
        "caisse.BonSortie",
        verbose_name="Bon de sortie",
        on_delete=models.SET_NULL,
        related_name="mouvements",
        null=True,
        blank=True
    )

    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Enregistré par",
        on_delete=models.PROTECT,
        related_name="mouvements_caisse"
    )

    date_operation = models.DateField(
        verbose_name="Date de l'opération"
    )

    date_creation = models.DateTimeField(
        verbose_name="Date d'enregistrement",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Mouvement de caisse"
        verbose_name_plural = "Mouvements de caisse"
        ordering = ["-date_operation", "-date_creation"]
        indexes = [
            models.Index(fields=["caisse", "-date_operation"]),
        ]

    def __str__(self):
        return (f"{self.caisse.code} — {self.get_type_mouvement_display()} "
                f"{self.montant:+}")

    def clean(self):
        if self.montant == 0:
            raise ValidationError({"montant": "Un mouvement nul n'a pas de sens."})

        entree = self.type_mouvement in self.TYPES_ENTREE
        if entree and self.montant < 0:
            raise ValidationError({
                "montant": "Une entrée en caisse se saisit en positif.",
            })
        if not entree and self.montant > 0:
            raise ValidationError({
                "montant": "Une sortie de caisse se saisit en négatif.",
            })

        # On n'alimente pas une caisse sur parole.
        if self.type_mouvement == self.TypeMouvement.ALIMENTATION:
            if not (self.justificatif or self.reference.strip()):
                raise ValidationError({
                    "justificatif": "Une alimentation exige une preuve : "
                                    "justificatif ou référence de transaction.",
                })


class BonSortie(models.Model):
    """
    Demande de sortie d'argent, adressée à une personne qui l'autorise.

    Le destinataire n'avance pas l'argent — il vient de la caisse — il
    autorise la dépense. Le transport fait exception : une course ne
    s'arbitre pas avant d'être payée.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente d'autorisation"
        AUTORISE = "AUTORISE", "Autorisé"
        REFUSE = "REFUSE", "Refusé"
        PAYE = "PAYE", "Payé"
        ANNULE = "ANNULE", "Annulé"

    class TypeDepense(models.TextChoices):
        TRANSPORT = "TRANSPORT", "Transport"
        AUTRE = "AUTRE", "Autre dépense"

    class MoyenTransport(models.TextChoices):
        TAXI = "TAXI", "Taxi"
        MOTO = "MOTO", "Moto"
        GOZEM = "GOZEM", "Gozem"

    #: Moyens dont l'opérateur conserve un historique de transaction : le
    #: justificatif est donc exigible, contrairement à une course payée en
    #: espèces à un taxi ou un zémidjan.
    MOYENS_AVEC_HISTORIQUE = (MoyenTransport.GOZEM,)

    reference = models.CharField(
        verbose_name="Référence",
        max_length=40,
        unique=True,
        editable=False
    )

    caisse = models.ForeignKey(
        "caisse.Caisse",
        verbose_name="Caisse",
        on_delete=models.PROTECT,
        related_name="bons_sortie"
    )

    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Demandeur",
        on_delete=models.PROTECT,
        related_name="bons_sortie"
    )

    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Adressé à",
        on_delete=models.PROTECT,
        related_name="bons_sortie_a_autoriser",
        null=True,
        blank=True,
        help_text="Personne qui autorise la dépense. Facultatif pour le "
                  "transport, qui se paie sans autorisation préalable."
    )

    objet = models.CharField(
        verbose_name="Objet",
        max_length=255
    )

    montant = models.DecimalField(
        verbose_name="Montant demandé",
        max_digits=14,
        decimal_places=2
    )

    type_depense = models.CharField(
        verbose_name="Type de dépense",
        max_length=20,
        choices=TypeDepense.choices,
        default=TypeDepense.AUTRE
    )

    moyen_transport = models.CharField(
        verbose_name="Moyen de transport",
        max_length=20,
        choices=MoyenTransport.choices,
        blank=True
    )

    justificatif = models.FileField(
        verbose_name="Justificatif",
        upload_to="caisse/bons/",
        null=True,
        blank=True
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE
    )

    etape_validation = models.PositiveSmallIntegerField(
        verbose_name="Étape de validation",
        default=0
    )

    motif_decision = models.TextField(
        verbose_name="Motif de la décision",
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
        verbose_name = "Bon de sortie"
        verbose_name_plural = "Bons de sortie"
        ordering = ["-date_creation"]
        indexes = [
            models.Index(fields=["caisse", "statut"]),
            models.Index(fields=["destinataire", "statut"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(montant__gt=0),
                name="bon_sortie_montant_positif",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.objet} ({self.montant})"

    @property
    def est_transport(self):
        return self.type_depense == self.TypeDepense.TRANSPORT

    @property
    def exige_justificatif(self):
        """
        Vrai pour les moyens dont l'opérateur garde une trace : Gozem
        conserve l'historique des courses, le justificatif est donc
        produisible. Un taxi payé en espèces n'en fournit pas.
        """
        return (self.est_transport
                and self.moyen_transport in self.MOYENS_AVEC_HISTORIQUE)

    @property
    def montant_paye(self):
        """Somme effectivement sortie de caisse pour ce bon."""
        total = self.mouvements.filter(
            type_mouvement=MouvementCaisse.TypeMouvement.SORTIE,
        ).aggregate(total=Sum("montant"))["total"]
        return abs(total) if total else Decimal("0")

    @property
    def montant_rendu(self):
        """Monnaie rendue en caisse après la dépense."""
        total = self.mouvements.filter(
            type_mouvement=MouvementCaisse.TypeMouvement.RETOUR,
        ).aggregate(total=Sum("montant"))["total"]
        return total or Decimal("0")

    @property
    def montant_consomme(self):
        """Ce que la dépense a réellement coûté, une fois la monnaie rendue."""
        return self.montant_paye - self.montant_rendu

    def clean(self):
        if self.montant is not None and self.montant <= 0:
            raise ValidationError({"montant": "Le montant doit être positif."})

        if self.est_transport:
            if not self.moyen_transport:
                raise ValidationError({
                    "moyen_transport": "Précisez le moyen de transport.",
                })
        elif self.moyen_transport:
            raise ValidationError({
                "moyen_transport": "Un moyen de transport ne se renseigne que "
                                   "sur une dépense de transport.",
            })
