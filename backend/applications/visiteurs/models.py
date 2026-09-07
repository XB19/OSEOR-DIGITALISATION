from django.conf import settings
from django.db import models


class Visite(models.Model):
    """
    Passage d'un visiteur à l'accueil : l'agent de sécurité enregistre son
    arrivée en échange de sa pièce d'identité, puis marque son départ quand
    il revient la récupérer. Une fois créée, seule l'action « marquer le
    départ » modifie l'entrée — pas d'édition libre, pour garder une trace
    fiable de qui est passé et quand.
    """

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
        max_length=60,
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

    @property
    def presente(self) -> bool:
        """Le visiteur est toujours sur place (sa pièce d'identité n'a pas été rendue)."""
        return self.heure_depart is None
