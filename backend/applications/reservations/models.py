from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from applications.salles.models import Salle


class Reservation(models.Model):
    """
    Demande de réservation d'une salle.
    """

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        VALIDEE = "VALIDEE", "Validée"
        REFUSEE = "REFUSEE", "Refusée"
        ANNULEE = "ANNULEE", "Annulée"
        DEPLACEE = "DEPLACEE", "Déplacée"
        TERMINEE = "TERMINEE", "Terminée"

    # Statuts qui occupent réellement un créneau (premier arrivé, premier servi - RG-01)
    STATUTS_ACTIFS = (Statut.EN_ATTENTE, Statut.VALIDEE)

    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="Demandeur"
    )

    nom_reservant = models.CharField(
        verbose_name="Nom du réservant",
        max_length=255
    )

    telephone = models.CharField(
        verbose_name="Téléphone du réservant",
        max_length=30,
        blank=True,
        help_text="Récupéré de l'AD en prod si disponible, sinon saisi (EF-03)."
    )

    serie = models.ForeignKey(
        "reservations.SerieRecurrence",
        on_delete=models.SET_NULL,
        related_name="occurrences",
        verbose_name="Série récurrente",
        null=True,
        blank=True
    )

    salle = models.ForeignKey(
        Salle,
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="Salle"
    )

    motif = models.CharField(
        verbose_name="Motif / objet de la réunion",
        max_length=255,
        blank=True,
        help_text="Objet de la réservation (ex. réunion d'équipe, entretien…)."
    )

    date_reunion = models.DateField(
        verbose_name="Date de réunion"
    )

    heure_debut = models.TimeField(
        verbose_name="Heure de début"
    )

    heure_fin = models.TimeField(
        verbose_name="Heure de fin"
    )

    precisions = models.TextField(
        verbose_name="Précisions spécifiques",
        blank=True,
        help_text=(
            "Café, boissons, collations, "
            "matériel supplémentaire, etc."
        )
    )

    statut = models.CharField(
        verbose_name="Statut",
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE
    )

    motif_refus = models.TextField(
        verbose_name="Motif du refus",
        blank=True
    )

    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations_validees",
        verbose_name="Validée par",
        null=True,
        blank=True
    )

    date_validation = models.DateTimeField(
        verbose_name="Date de validation",
        null=True,
        blank=True
    )

    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations_annulees",
        verbose_name="Annulée par",
        null=True,
        blank=True
    )

    date_annulation = models.DateTimeField(
        verbose_name="Date d'annulation",
        null=True,
        blank=True
    )

    motif_annulation = models.TextField(
        verbose_name="Motif d'annulation",
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
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = [
            "-date_reunion",
            "-heure_debut"
        ]

        indexes = [
            models.Index(
                fields=[
                    "salle",
                    "date_reunion"
                ]
            )
        ]

    def clean(self):
        """
        Vérification des règles métier.
        """

        if self.heure_debut >= self.heure_fin:
            raise ValidationError(
                "L'heure de fin doit être supérieure à l'heure de début."
            )

        reservations_conflit = Reservation.objects.filter(
            salle=self.salle,
            date_reunion=self.date_reunion,
            statut__in=self.STATUTS_ACTIFS
        )

        if self.pk:
            reservations_conflit = reservations_conflit.exclude(
                pk=self.pk
            )

        for reservation in reservations_conflit:

            if (
                self.heure_debut < reservation.heure_fin
                and
                self.heure_fin > reservation.heure_debut
            ):
                raise ValidationError(
                    "Cette salle est déjà réservée sur ce créneau."
                )

    def save(self, *args, **kwargs):
        """
        Validation automatique avant sauvegarde.
        """

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.nom_reservant} - "
            f"{self.salle.nom} - "
            f"{self.date_reunion}"
        )


class Participant(models.Model):
    """
    Personne conviée à la réunion (liste de présence — EF-04).

    Permet à l'accueil de recevoir les bonnes personnes dans la bonne salle
    et de distinguer les participants internes (du groupe) des externes.
    """

    class Type(models.TextChoices):
        INTERNE = "INTERNE", "Interne (membre du groupe)"
        EXTERNE = "EXTERNE", "Externe"

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Réservation"
    )

    nom = models.CharField(
        verbose_name="Nom",
        max_length=150
    )

    prenom = models.CharField(
        verbose_name="Prénom",
        max_length=150,
        blank=True
    )

    email = models.EmailField(
        verbose_name="Email",
        blank=True
    )

    telephone = models.CharField(
        verbose_name="Téléphone",
        max_length=30,
        blank=True
    )

    societe = models.CharField(
        verbose_name="Société / filiale d'appartenance",
        max_length=150,
        blank=True,
        help_text="Entreprise ou filiale d'origine. "
                  "Laisser vide pour un participant externe sans société du groupe."
    )

    type_participant = models.CharField(
        verbose_name="Type",
        max_length=10,
        choices=Type.choices,
        default=Type.INTERNE
    )

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="participations",
        verbose_name="Utilisateur interne lié",
        null=True,
        blank=True,
        help_text="Renseigné pour un participant interne sélectionné dans "
                  "l'annuaire (sert à la convocation automatique — RG-13)."
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de création",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Participant"
        verbose_name_plural = "Participants"
        ordering = ["nom", "prenom"]

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    def __str__(self):
        return self.nom_complet


class SerieRecurrence(models.Model):
    """
    Série de réservations récurrentes (EF-08).

    Décrit la règle de répétition (ex. chaque lundi 9h-10h jusqu'au 30/06).
    Chaque occurrence générée est une Reservation reliée à la série
    (Reservation.serie). Le contrôle de chevauchement s'applique à chaque
    occurrence : celles en conflit sont signalées et exclues / laissées à
    l'arbitrage du secrétariat.
    """

    class Frequence(models.TextChoices):
        QUOTIDIENNE = "QUOTIDIENNE", "Tous les jours (ouvrés)"
        HEBDOMADAIRE = "HEBDOMADAIRE", "Chaque semaine"
        BIHEBDOMADAIRE = "BIHEBDOMADAIRE", "Une semaine sur deux"
        MENSUELLE = "MENSUELLE", "Chaque mois"

    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="series_recurrence",
        verbose_name="Demandeur"
    )

    nom_reservant = models.CharField(
        verbose_name="Nom du réservant",
        max_length=255
    )

    telephone = models.CharField(
        verbose_name="Téléphone du réservant",
        max_length=30,
        blank=True
    )

    motif = models.CharField(
        verbose_name="Motif / objet de la réunion",
        max_length=255,
        blank=True
    )

    salle = models.ForeignKey(
        Salle,
        on_delete=models.PROTECT,
        related_name="series_recurrence",
        verbose_name="Salle"
    )

    frequence = models.CharField(
        verbose_name="Fréquence",
        max_length=20,
        choices=Frequence.choices,
        default=Frequence.HEBDOMADAIRE
    )

    jours_semaine = models.JSONField(
        verbose_name="Jours de la semaine",
        default=list,
        blank=True,
        help_text="Liste d'entiers 0=lundi … 6=dimanche "
                  "(pour les fréquences hebdomadaires)."
    )

    heure_debut = models.TimeField(
        verbose_name="Heure de début"
    )

    heure_fin = models.TimeField(
        verbose_name="Heure de fin"
    )

    date_debut = models.DateField(
        verbose_name="Date de début de la série"
    )

    date_fin = models.DateField(
        verbose_name="Date de fin de la série"
    )

    precisions = models.TextField(
        verbose_name="Précisions spécifiques",
        blank=True
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de création",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Série récurrente"
        verbose_name_plural = "Séries récurrentes"
        ordering = ["-date_creation"]

    def __str__(self):
        return (
            f"Série {self.get_frequence_display()} - "
            f"{self.salle.nom} ({self.date_debut} → {self.date_fin})"
        )