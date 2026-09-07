from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

_VALIDATEUR_NUMERO_PIECE = RegexValidator(
    r"^\d+$", "Le numéro de pièce d'identité ne doit contenir que des chiffres."
)


class Visite(models.Model):
    """
    Passage d'un visiteur à l'accueil : l'agent de sécurité enregistre sa
    demande (en échange de sa pièce d'identité), la secrétaire la valide ou
    la refuse, puis l'agent marque le départ quand le visiteur revient
    récupérer sa pièce. Même circuit que les réservations de salles
    (EN_ATTENTE -> VALIDEE/REFUSEE), adapté à deux acteurs seulement.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente de validation"
        VALIDEE = "VALIDEE", "Validée"
        REFUSEE = "REFUSEE", "Refusée"
        TERMINEE = "TERMINEE", "Terminée"

    nom = models.CharField(
        verbose_name="Nom",
        max_length=100,
    )

    prenom = models.CharField(
        verbose_name="Prénom",
        max_length=100,
    )

    numero_piece = models.CharField(
        verbose_name="Numéro de pièce d'identité",
        max_length=30,
        validators=[_VALIDATEUR_NUMERO_PIECE],
    )

    motif = models.CharField(
        verbose_name="Motif de la visite",
        max_length=255,
        default="",
    )

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.PROTECT,
        related_name="visites",
    )

    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Enregistré par",
        on_delete=models.PROTECT,
        related_name="visites_enregistrees",
    )

    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Traité par",
        on_delete=models.PROTECT,
        related_name="visites_traitees",
        null=True,
        blank=True,
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
    )

    motif_refus = models.CharField(
        verbose_name="Motif du refus",
        max_length=255,
        blank=True,
        default="",
    )

    heure_arrivee = models.DateTimeField(
        verbose_name="Heure d'arrivée",
        auto_now_add=True,
    )

    heure_depart = models.DateTimeField(
        verbose_name="Heure de départ",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Visite"
        verbose_name_plural = "Visites"
        ordering = ["-heure_arrivee"]

    def __str__(self):
        return f"{self.prenom} {self.nom} — {self.heure_arrivee:%d/%m/%Y %H:%M}"
