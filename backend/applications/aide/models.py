from django.db import models


class EntreeAide(models.Model):
    """
    Question/réponse du chatbot d'aide : guide un utilisateur bloqué sur
    une action (« comment réserver une salle ? ») vers une réponse claire,
    sans intervention d'un collègue ou du service informatique.
    """

    class Module(models.TextChoices):
        RESERVATIONS = "RESERVATIONS", "Réservations de salles"
        AUDIENCES = "AUDIENCES", "Audiences"
        DOCUMENTS = "DOCUMENTS", "Documents administratifs"
        CONGES = "CONGES", "Congés"
        CONTRATS = "CONTRATS", "Contrats"
        PRESTATIONS = "PRESTATIONS", "Prestations de services"
        STOCKS = "STOCKS", "Gestion de stocks"
        NOTES = "NOTES", "Notes internes"
        UTILISATEURS = "UTILISATEURS", "Utilisateurs et administration"
        GENERAL = "GENERAL", "Général"

    module = models.CharField(
        verbose_name="Module",
        max_length=20,
        choices=Module.choices,
    )

    question = models.CharField(
        verbose_name="Question",
        max_length=255,
    )

    mots_cles = models.CharField(
        verbose_name="Mots-clés",
        max_length=500,
        help_text="Mots ou expressions séparés par des virgules, utilisés pour retrouver cette réponse.",
    )

    reponse = models.TextField(
        verbose_name="Réponse",
    )

    ordre = models.PositiveIntegerField(
        verbose_name="Ordre",
        default=0,
    )

    actif = models.BooleanField(
        verbose_name="Actif",
        default=True,
    )

    class Meta:
        verbose_name = "Entrée d'aide"
        verbose_name_plural = "Entrées d'aide"
        ordering = ["module", "ordre"]

    def __str__(self):
        return self.question
