"""
Procédures disciplinaires : faits, explications du salarié, sanction.

Le dossier disciplinaire est la donnée la plus sensible de
l'application. Son périmètre de lecture est volontairement le plus étroit
du projet : le salarié concerné, les RH et la direction. Ni les collègues,
ni le chef de service, ni la comptabilité.

Rien ne s'efface ici. Une procédure classée sans suite reste au dossier
avec son motif — c'est ce qui permet de montrer qu'elle a été classée.
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .convention import (
    DELAI_SANCTION_MOIS, FAUTES_LOURDES, choix_sanctions, regle,
)


class ProcedureDisciplinaire(models.Model):
    """
    Un dossier ouvert à la suite de faits reprochés à un salarié.

    `date_preuve` fait courir le délai de deux mois de l'article 58 : c'est
    la date à laquelle la preuve de la faute a été établie, pas celle des
    faits ni celle de l'ouverture du dossier. La distinction compte — une
    faute découverte tardivement reste sanctionnable.
    """

    class Statut(models.TextChoices):
        OUVERTE = "OUVERTE", "Ouverte"
        EXPLICATIONS_DEMANDEES = "EXPLICATIONS_DEMANDEES", "Explications demandées"
        EXPLICATIONS_FOURNIES = "EXPLICATIONS_FOURNIES", "Explications fournies"
        SANCTIONNEE = "SANCTIONNEE", "Sanction prononcée"
        CLASSEE = "CLASSEE", "Classée sans suite"

    class Qualification(models.TextChoices):
        FAUTE_SIMPLE = "FAUTE_SIMPLE", "Faute professionnelle"
        FAUTE_LOURDE = "FAUTE_LOURDE", "Faute lourde"

    reference = models.CharField(
        verbose_name="Référence",
        max_length=40,
        unique=True,
        editable=False
    )

    salarie = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Salarié concerné",
        on_delete=models.PROTECT,
        related_name="procedures_disciplinaires"
    )

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.PROTECT,
        related_name="procedures_disciplinaires"
    )

    faits = models.TextField(
        verbose_name="Faits reprochés"
    )

    date_faits = models.DateField(
        verbose_name="Date des faits"
    )

    date_preuve = models.DateField(
        verbose_name="Date d'établissement de la preuve",
        help_text="Point de départ du délai de deux mois de l'article 58."
    )

    qualification = models.CharField(
        verbose_name="Qualification",
        max_length=20,
        choices=Qualification.choices,
        default=Qualification.FAUTE_SIMPLE
    )

    faute_lourde_invoquee = models.CharField(
        verbose_name="Faute lourde invoquée",
        max_length=40,
        blank=True,
        choices=FAUTES_LOURDES,
        help_text="Énumération de l'article 58. La liste n'étant pas "
                  "limitative, un cas non listé se décrit dans les faits."
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=30,
        choices=Statut.choices,
        default=Statut.OUVERTE
    )

    mise_a_pied_conservatoire = models.BooleanField(
        verbose_name="Mise à pied conservatoire",
        default=False,
        help_text="Mesure d'attente, le temps d'instruire. N'est pas une "
                  "sanction et ne préjuge d'aucune."
    )

    date_mise_a_pied = models.DateField(
        verbose_name="Début de la mise à pied conservatoire",
        null=True,
        blank=True
    )

    ouverte_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Ouverte par",
        on_delete=models.PROTECT,
        related_name="procedures_ouvertes"
    )

    motif_classement = models.TextField(
        verbose_name="Motif du classement",
        blank=True
    )

    date_ouverture = models.DateTimeField(
        verbose_name="Date d'ouverture",
        auto_now_add=True
    )

    date_modification = models.DateTimeField(
        verbose_name="Dernière modification",
        auto_now=True
    )

    class Meta:
        verbose_name = "Procédure disciplinaire"
        verbose_name_plural = "Procédures disciplinaires"
        ordering = ["-date_ouverture"]
        indexes = [
            models.Index(fields=["salarie", "-date_ouverture"]),
            models.Index(fields=["statut"]),
        ]

    def __str__(self):
        return f"{self.reference} — {self.salarie.nom_complet}"

    @property
    def date_limite_sanction(self):
        """
        Échéance au-delà de laquelle plus aucune sanction n'est possible.

        Deux mois à compter de l'établissement de la preuve (article 58).
        Calculé en jours plutôt qu'en mois calendaires : la règle protège
        le salarié, mieux vaut l'appliquer strictement.
        """
        return self.date_preuve + timedelta(days=DELAI_SANCTION_MOIS * 30)

    @property
    def delai_depasse(self):
        from datetime import date

        return date.today() > self.date_limite_sanction

    @property
    def est_close(self):
        return self.statut in (self.Statut.SANCTIONNEE, self.Statut.CLASSEE)

    @property
    def explications_recueillies(self):
        return self.explications.exists()

    def clean(self):
        if self.date_preuve and self.date_faits:
            if self.date_preuve < self.date_faits:
                raise ValidationError({
                    "date_preuve": "La preuve ne peut pas précéder les faits.",
                })

        if (self.qualification == self.Qualification.FAUTE_SIMPLE
                and self.faute_lourde_invoquee):
            raise ValidationError({
                "faute_lourde_invoquee": "Une faute lourde invoquée impose la "
                                         "qualification correspondante.",
            })


class ExplicationSalarie(models.Model):
    """
    Explications du salarié, préalable obligatoire à toute sanction.

    L'article 58 les veut « écrites ou verbales », le salarié pouvant être
    « assisté éventuellement de son délégué du personnel ». Les explications
    verbales sont donc recevables : on consigne alors leur teneur et la
    présence éventuelle du délégué.
    """

    class Mode(models.TextChoices):
        ECRITE = "ECRITE", "Écrites"
        VERBALE = "VERBALE", "Verbales, consignées"
        REFUS = "REFUS", "Le salarié a refusé de s'expliquer"

    procedure = models.ForeignKey(
        "discipline.ProcedureDisciplinaire",
        verbose_name="Procédure",
        on_delete=models.CASCADE,
        related_name="explications"
    )

    mode = models.CharField(
        verbose_name="Mode",
        max_length=20,
        choices=Mode.choices,
        default=Mode.ECRITE
    )

    contenu = models.TextField(
        verbose_name="Teneur des explications",
        blank=True
    )

    piece_jointe = models.FileField(
        verbose_name="Pièce jointe",
        upload_to="discipline/explications/",
        null=True,
        blank=True
    )

    delegue_present = models.BooleanField(
        verbose_name="Salarié assisté d'un délégué du personnel",
        default=False
    )

    consignee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Consignée par",
        on_delete=models.PROTECT,
        related_name="explications_consignees"
    )

    date_explication = models.DateTimeField(
        verbose_name="Date",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Explications du salarié"
        verbose_name_plural = "Explications des salariés"
        ordering = ["date_explication"]

    def __str__(self):
        return f"{self.procedure.reference} — {self.get_mode_display()}"


class Sanction(models.Model):
    """
    Sanction prononcée au terme d'une procédure.

    Relation **un-à-un** avec la procédure : « la même faute ne peut faire
    l'objet de deux sanctions » (article 58). La contrainte est portée par
    le schéma, pas seulement par le code — c'est une garantie donnée au
    salarié, elle mérite mieux qu'une vérification applicative.
    """

    procedure = models.OneToOneField(
        "discipline.ProcedureDisciplinaire",
        verbose_name="Procédure",
        on_delete=models.PROTECT,
        related_name="sanction"
    )

    type_sanction = models.CharField(
        verbose_name="Sanction",
        max_length=40,
        choices=choix_sanctions()
    )

    duree_jours = models.PositiveSmallIntegerField(
        verbose_name="Durée (jours)",
        null=True,
        blank=True,
        help_text="Pour les mises à pied : 1 à 8 jours, 1 à 15 en cas "
                  "d'aggravation."
    )

    motif = models.TextField(
        verbose_name="Motivation de la sanction"
    )

    prononcee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Prononcée par",
        on_delete=models.PROTECT,
        related_name="sanctions_prononcees"
    )

    date_prononce = models.DateField(
        verbose_name="Date du prononcé"
    )

    date_notification = models.DateField(
        verbose_name="Signifiée au salarié le",
        null=True,
        blank=True
    )

    date_inspection_travail = models.DateField(
        verbose_name="Ampliation à l'Inspection du Travail le",
        null=True,
        blank=True,
        help_text="L'article 58 impose d'adresser ampliation de la décision "
                  "à l'Inspecteur du Travail du ressort."
    )

    date_creation = models.DateTimeField(
        verbose_name="Date d'enregistrement",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Sanction disciplinaire"
        verbose_name_plural = "Sanctions disciplinaires"
        ordering = ["-date_prononce"]

    def __str__(self):
        return f"{self.procedure.reference} — {self.get_type_sanction_display()}"

    @property
    def formalites_completes(self):
        """
        Les deux formalités que l'article 58 impose après le prononcé :
        signification au salarié et ampliation à l'Inspection du Travail.
        """
        return bool(self.date_notification and self.date_inspection_travail)

    @property
    def libelle_bareme(self):
        r = regle(self.type_sanction)
        return r["libelle"] if r else self.type_sanction
