from django.conf import settings
from django.db import models


class LectureNote(models.Model):
    """
    Un destinataire d'une note interne, et la date à laquelle il l'a lue.

    Cette table joue deux rôles à la fois : elle EST la liste de diffusion
    (une ligne par destinataire, créée à la signature de la note) et elle
    porte l'accusé de lecture. C'est ce qui permet de répondre à « qui n'a
    pas encore pris connaissance de la note ? » — impossible avec une note
    de service affichée sur un panneau.

    L'existence de lignes pour une note vaut donc « note déjà diffusée » :
    la diffusion n'a pas besoin d'un drapeau supplémentaire.
    """

    note = models.ForeignKey(
        "documents.Document",
        verbose_name="Note interne",
        on_delete=models.CASCADE,
        related_name="lectures"
    )

    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Destinataire",
        on_delete=models.CASCADE,
        related_name="notes_recues"
    )

    date_diffusion = models.DateTimeField(
        verbose_name="Date de diffusion",
        auto_now_add=True
    )

    date_lecture = models.DateTimeField(
        verbose_name="Date de lecture",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Lecture de note interne"
        verbose_name_plural = "Lectures de notes internes"
        ordering = ["-date_diffusion"]
        constraints = [
            models.UniqueConstraint(
                fields=["note", "destinataire"],
                name="lecture_note_unique_par_destinataire",
            ),
        ]
        indexes = [
            models.Index(fields=["destinataire", "date_lecture"]),
        ]

    def __str__(self):
        etat = "lue" if self.date_lecture else "non lue"
        return f"{self.note.numero} → {self.destinataire.nom_complet} ({etat})"

    @property
    def lue(self):
        return self.date_lecture is not None
