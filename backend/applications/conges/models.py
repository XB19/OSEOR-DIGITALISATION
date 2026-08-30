"""
Congés : jours fériés, mouvements de solde et demandes.

Règles retenues avec les RH :

- acquisition de **2,5 jours par mois de service révolu, à compter de la
  date d'embauche** (Code du travail togolais 2021, art. 200 à 202) ;
- les jours non pris **se cumulent sans limite de temps** et ne sont
  jamais perdus en fin d'année (décision OSEOR du 2026-08-24). La loi
  n'impose qu'un report de deux ans d'accord-parties : le groupe fait
  donc plus favorable que le minimum légal. Le plafond reste activable
  d'un réglage, `CONGES_REPORT_MAX_ANNEES` ;
- **pas de demi-journées** : une demande porte sur des jours entiers ;
- les **permissions exceptionnelles** (article 45 de la Convention
  Collective Interprofessionnelle du Togo) ne se déduisent jamais du
  congé annuel — voir `convention.py` ;
- jours fériés du **Togo**.

Le solde n'est jamais stocké comme un compteur : il se calcule en
additionnant les `MouvementConge`. Un compteur modifié en place dérive au
premier incident (tâche rejouée, requête concurrente, correction a
posteriori) et devient impossible à justifier devant un salarié. Le
registre, lui, dit toujours d'où vient chaque jour.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class JourFerie(models.Model):
    """
    Jour férié chômé.

    Table de données, et non liste figée dans le code : les fêtes
    musulmanes (Aïd el-Fitr, Aïd el-Adha) suivent le calendrier lunaire et
    sont fixées chaque année par décret — elles doivent pouvoir être
    saisies sans redéploiement. `seed_jours_feries` pose les dates fixes et
    celles qui se déduisent de Pâques.
    """

    date = models.DateField(
        verbose_name="Date"
    )

    nom = models.CharField(
        verbose_name="Intitulé",
        max_length=150
    )

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.CASCADE,
        related_name="jours_feries",
        null=True,
        blank=True,
        help_text="Vide = applicable à tout le groupe."
    )

    class Meta:
        verbose_name = "Jour férié"
        verbose_name_plural = "Jours fériés"
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "filiale"],
                name="jour_ferie_unique_par_date_et_filiale",
            ),
        ]
        indexes = [
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        return f"{self.date:%d/%m/%Y} — {self.nom}"


class TypeConge(models.TextChoices):
    ANNUEL = "ANNUEL", "Congé annuel"
    PERMISSION = "PERMISSION", "Permission exceptionnelle"
    MALADIE = "MALADIE", "Congé maladie"
    MATERNITE = "MATERNITE", "Congé de maternité"
    SANS_SOLDE = "SANS_SOLDE", "Congé sans solde"


#: Seul le congé annuel se décompte du solde acquis.
#:
#: Les permissions exceptionnelles en sont exclues par l'article 45 de la
#: CCIT, qui les dit « non déductibles du congé annuel et n'entraînant
#: aucune réduction de salaire ». Les congés maladie et maternité relèvent
#: d'un régime propre.
TYPES_DECOMPTES = (TypeConge.ANNUEL,)


class DemandeConge(models.Model):
    """Demande de congé d'un salarié, et son parcours de validation."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente de validation"
        VALIDEE = "VALIDEE", "Validée"
        REFUSEE = "REFUSEE", "Refusée"
        ANNULEE = "ANNULEE", "Annulée"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Salarié",
        on_delete=models.PROTECT,
        related_name="demandes_conge"
    )

    type_conge = models.CharField(
        verbose_name="Type de congé",
        max_length=20,
        choices=TypeConge.choices,
        default=TypeConge.ANNUEL
    )

    date_debut = models.DateField(
        verbose_name="Du"
    )

    date_fin = models.DateField(
        verbose_name="Au"
    )

    jours_ouvres = models.PositiveSmallIntegerField(
        verbose_name="Jours ouvrés décomptés",
        default=0,
        help_text="Calculé à la création : week-ends et jours fériés exclus."
    )

    motif_permission = models.CharField(
        verbose_name="Motif de la permission",
        max_length=30,
        blank=True,
        help_text="Évènement ouvrant droit à permission (article 45 de la CCIT)."
    )

    justificatif = models.FileField(
        verbose_name="Justificatif",
        upload_to="conges/justificatifs/",
        null=True,
        blank=True,
        help_text="Acte d'état civil ou convocation, à produire sous 8 jours."
    )

    date_evenement = models.DateField(
        verbose_name="Date de l'évènement",
        null=True,
        blank=True,
        help_text="Date du décès, du mariage, de la naissance… Fait courir "
                  "le délai de production du justificatif."
    )

    motif = models.TextField(
        verbose_name="Motif",
        blank=True
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE
    )

    etape_validation = models.PositiveSmallIntegerField(
        verbose_name="Étape de validation courante",
        default=0,
        help_text="Rang dans le circuit applicable (voir circuits.py)."
    )

    valideur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Validé / refusé par",
        on_delete=models.SET_NULL,
        related_name="demandes_conge_traitees",
        null=True,
        blank=True
    )

    date_decision = models.DateTimeField(
        verbose_name="Date de décision",
        null=True,
        blank=True
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
        verbose_name = "Demande de congé"
        verbose_name_plural = "Demandes de congé"
        ordering = ["-date_debut"]
        indexes = [
            models.Index(fields=["utilisateur", "statut"]),
            models.Index(fields=["date_debut"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_fin__gte=models.F("date_debut")),
                name="demande_conge_fin_apres_debut",
            ),
        ]

    def __str__(self):
        return (f"{self.utilisateur.nom_complet} — "
                f"{self.date_debut:%d/%m/%Y} au {self.date_fin:%d/%m/%Y}")

    @property
    def est_en_cours(self):
        """Une demande qui mobilise encore des jours du solde."""
        return self.statut in (self.Statut.EN_ATTENTE, self.Statut.VALIDEE)

    @property
    def decompte_le_solde(self):
        return self.type_conge in TYPES_DECOMPTES

    @property
    def est_permission(self):
        return self.type_conge == TypeConge.PERMISSION

    @property
    def regle_permission(self):
        """Règle conventionnelle applicable, ou None hors permission."""
        from .convention import regle

        if not self.est_permission:
            return None
        return regle(self.motif_permission)

    @property
    def justificatif_attendu(self):
        """
        Libellé de la pièce à produire — l'article 45 impose de la fournir
        « au plus tard huit jours après que l'évènement ait eu lieu ».
        """
        regle_motif = self.regle_permission
        return regle_motif["justificatif"] if regle_motif else ""

    @property
    def date_limite_justificatif(self):
        """Échéance de production du justificatif, à partir de l'évènement."""
        from datetime import timedelta

        from .convention import DELAI_JUSTIFICATIF_JOURS

        reference = self.date_evenement or self.date_debut
        if not self.est_permission or reference is None:
            return None
        return reference + timedelta(days=DELAI_JUSTIFICATIF_JOURS)

    @property
    def justificatif_en_retard(self):
        """
        True si le délai de huit jours est dépassé sans pièce fournie.

        Ne bloque rien : la permission reste acquise, c'est un signalement
        pour les RH — l'article 45 fixe un délai, pas une déchéance
        automatique.
        """
        from datetime import date

        if not self.est_permission or self.justificatif:
            return False
        limite = self.date_limite_justificatif
        return limite is not None and limite < date.today()

    def clean(self):
        from .convention import regle

        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError({
                "date_fin": "La fin ne peut pas précéder le début.",
            })

        if self.type_conge == TypeConge.PERMISSION:
            if not self.motif_permission:
                raise ValidationError({
                    "motif_permission": "Une permission exceptionnelle doit "
                                        "préciser l'évènement invoqué.",
                })
            if regle(self.motif_permission) is None:
                raise ValidationError({
                    "motif_permission": "Motif inconnu au barème de "
                                        "l'article 45.",
                })
        elif self.motif_permission:
            raise ValidationError({
                "motif_permission": "Un motif de permission ne se renseigne "
                                    "que sur une permission exceptionnelle.",
            })


class MouvementConge(models.Model):
    """
    Écriture au registre des congés : chaque jour crédité ou consommé
    laisse une ligne, jamais effacée.

    Le solde d'un salarié est la somme de ses mouvements sur l'année. Une
    correction se fait en ajoutant une écriture inverse, comme en
    comptabilité — jamais en retouchant l'historique.
    """

    class TypeMouvement(models.TextChoices):
        ACQUISITION = "ACQUISITION", "Acquisition mensuelle"
        CONSOMMATION = "CONSOMMATION", "Congé pris"
        RESTITUTION = "RESTITUTION", "Restitution (annulation)"
        EXPIRATION = "EXPIRATION", "Solde perdu en fin d'année"
        CORRECTION = "CORRECTION", "Correction manuelle"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Salarié",
        on_delete=models.PROTECT,
        related_name="mouvements_conge"
    )

    annee = models.PositiveSmallIntegerField(
        verbose_name="Année de rattachement"
    )

    type_mouvement = models.CharField(
        verbose_name="Type",
        max_length=20,
        choices=TypeMouvement.choices
    )

    jours = models.DecimalField(
        verbose_name="Jours",
        max_digits=6,
        decimal_places=2,
        help_text="Positif pour un crédit, négatif pour un débit."
    )

    date_effet = models.DateField(
        verbose_name="Date d'effet"
    )

    demande = models.ForeignKey(
        "conges.DemandeConge",
        verbose_name="Demande liée",
        on_delete=models.SET_NULL,
        related_name="mouvements",
        null=True,
        blank=True
    )

    motif = models.CharField(
        verbose_name="Motif",
        max_length=255,
        blank=True
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de création",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Mouvement de congé"
        verbose_name_plural = "Mouvements de congé"
        ordering = ["-date_effet", "-date_creation"]
        indexes = [
            models.Index(fields=["utilisateur", "annee"]),
        ]
        constraints = [
            # Garde-fou d'idempotence : la tâche mensuelle est rejouable
            # (ACKS_LATE), et une acquisition créditée deux fois pour le
            # même mois donnerait des jours qui n'existent pas.
            models.UniqueConstraint(
                fields=["utilisateur", "type_mouvement", "date_effet"],
                condition=models.Q(type_mouvement="ACQUISITION"),
                name="une_seule_acquisition_par_mois",
            ),
        ]

    def __str__(self):
        return (f"{self.utilisateur.nom_complet} — {self.get_type_mouvement_display()} "
                f"{self.jours:+} j ({self.date_effet:%d/%m/%Y})")
