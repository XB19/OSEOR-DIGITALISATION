from django.db import models
from django.conf import settings


class Audience(models.Model):
    """
    Fiche d'audience (EF-12) — demande d'audience d'un visiteur externe
    auprès d'un DG, reproduite d'après la « FICHE D'AUDIENCE » papier.

    Saisie par la secrétaire pour le compte du visiteur, puis navette
    avec le DG (EF-13) jusqu'à validation, et confirmation finale (EF-17).
    Une audience validée nécessite une salle et un créneau (RG-10) :
    le lien vers la réservation est porté par `reservation`.
    """

    class Statut(models.TextChoices):
        SAISIE = "SAISIE", "Saisie"
        ENVOYEE_DG = "ENVOYEE_DG", "Envoyée au DG"
        RENVOYEE_SECRETAIRE = "RENVOYEE_SECRETAIRE", "Renvoyée à la secrétaire"
        VALIDEE_DG = "VALIDEE_DG", "Validée par le DG"
        CONFIRMEE = "CONFIRMEE", "Confirmée"
        ANNULEE = "ANNULEE", "Annulée"
        TERMINEE = "TERMINEE", "Terminée"

    # --- Identité du visiteur (champs de la fiche papier) ---
    nom = models.CharField(
        verbose_name="Nom",
        max_length=150
    )

    prenom = models.CharField(
        verbose_name="Prénom",
        max_length=150,
        blank=True
    )

    profession = models.CharField(
        verbose_name="Profession",
        max_length=200,
        blank=True
    )

    contact = models.CharField(
        verbose_name="Contact (téléphone / email)",
        max_length=200,
        blank=True
    )

    objet_visite = models.TextField(
        verbose_name="Objet de la visite"
    )

    # --- Workflow ---
    secretaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audiences_saisies",
        verbose_name="Secrétaire (saisie)"
    )

    dg = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audiences_recues",
        verbose_name="DG destinataire"
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=25,
        choices=Statut.choices,
        default=Statut.SAISIE
    )

    # --- Planification (salle + créneau, RG-10) ---
    date_souhaitee = models.DateField(
        verbose_name="Date souhaitée",
        null=True,
        blank=True
    )

    heure_debut = models.TimeField(
        verbose_name="Heure de début",
        null=True,
        blank=True
    )

    heure_fin = models.TimeField(
        verbose_name="Heure de fin",
        null=True,
        blank=True
    )

    salle = models.ForeignKey(
        "salles.Salle",
        on_delete=models.SET_NULL,
        related_name="audiences",
        verbose_name="Salle",
        null=True,
        blank=True,
        help_text="Optionnel : seulement si l'audience a lieu dans une salle de réunion."
    )

    lieu = models.CharField(
        verbose_name="Lieu (hors salle)",
        max_length=200,
        blank=True,
        help_text="Si pas de salle : ex. « Bureau du DG », « Bureau du délégué »."
    )

    reservation = models.OneToOneField(
        "reservations.Reservation",
        on_delete=models.SET_NULL,
        related_name="audience",
        verbose_name="Réservation de salle liée",
        null=True,
        blank=True
    )

    date_confirmation = models.DateTimeField(
        verbose_name="Date de confirmation",
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
        verbose_name = "Audience"
        verbose_name_plural = "Audiences"
        ordering = ["-date_creation"]

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    def __str__(self):
        return f"Audience {self.nom_complet} → {self.dg}"


class EchangeAudience(models.Model):
    """
    Message de la navette secrétaire ↔ DG (EF-13).

    Le DG peut renvoyer la fiche à la secrétaire avec un commentaire pour
    complément d'information ; l'historique des échanges est conservé.
    """

    audience = models.ForeignKey(
        Audience,
        on_delete=models.CASCADE,
        related_name="echanges",
        verbose_name="Audience"
    )

    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="echanges_audience",
        verbose_name="Auteur"
    )

    commentaire = models.TextField(
        verbose_name="Commentaire"
    )

    date_creation = models.DateTimeField(
        verbose_name="Date",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Échange d'audience"
        verbose_name_plural = "Échanges d'audience"
        ordering = ["date_creation"]

    def __str__(self):
        return f"Échange {self.audience_id} par {self.auteur}"


class Delegation(models.Model):
    """
    Délégation d'une audience par le DG à un ou plusieurs collaborateurs
    (EF-14). Le délégué ne peut pas refuser : la délégation est effective
    dès sa prise de connaissance (EF-15 / RG-11), et le DG est notifié.
    """

    class Statut(models.TextChoices):
        PROPOSEE = "PROPOSEE", "Proposée"
        PRISE_EN_COMPTE = "PRISE_EN_COMPTE", "Prise en compte"

    audience = models.ForeignKey(
        Audience,
        on_delete=models.CASCADE,
        related_name="delegations",
        verbose_name="Audience"
    )

    delegue = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delegations_recues",
        verbose_name="Délégué"
    )

    commentaire = models.TextField(
        verbose_name="Commentaire du DG",
        blank=True,
        help_text="Ex. « Paul s'occupera de recevoir le client »."
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.PROPOSEE
    )

    date_proposition = models.DateTimeField(
        verbose_name="Date de proposition",
        auto_now_add=True
    )

    date_prise_en_compte = models.DateTimeField(
        verbose_name="Date de prise en compte",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Délégation"
        verbose_name_plural = "Délégations"
        ordering = ["-date_proposition"]
        constraints = [
            models.UniqueConstraint(
                fields=["audience", "delegue"],
                name="unique_delegue_par_audience"
            )
        ]

    def __str__(self):
        return f"Délégation {self.audience_id} → {self.delegue}"
