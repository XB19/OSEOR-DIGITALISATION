"""
Galerie / Mémoire : albums photo de la vie du groupe.

Stockage local (`MEDIA_ROOT`, volume Docker `media_data`), servi par nginx.
Le jour où le volume ne suffira plus, seul le `STORAGES` de Django est à
changer : rien ici ne suppose un chemin sur disque.

Deux garde-fous à l'entrée, parce qu'un album photo est le seul module du
projet capable de remplir un disque : une taille maximale par fichier, et
une limite de dimensions qui arrête les images-bombes (quelques kilo-octets
compressés, plusieurs gigaoctets décompressés en mémoire).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

#: Taille maximale d'un fichier téléversé.
TAILLE_MAX_OCTETS = 10 * 1024 * 1024  # 10 Mo

#: Au-delà, l'image est refusée : une photo d'appareil dépasse rarement
#: 8000 px de côté, et décompresser plus expose à une saturation mémoire.
DIMENSIONS_MAX = (8000, 8000)

#: Taille de la vignette générée à l'enregistrement. Sans elle, afficher un
#: album de 200 photos ferait télécharger 200 fichiers pleine résolution.
MINIATURE = (480, 480)

FORMATS_ACCEPTES = ("JPEG", "PNG", "GIF", "WEBP")


def valider_taille_image(fichier):
    if fichier.size > TAILLE_MAX_OCTETS:
        maxi = TAILLE_MAX_OCTETS // (1024 * 1024)
        raise ValidationError(
            f"Fichier trop volumineux ({fichier.size // 1024} Ko) : "
            f"{maxi} Mo maximum."
        )


class Album(models.Model):
    """
    Album photo, rattaché à une filiale et éventuellement à un événement —
    c'est ce lien qui fait la « mémoire » : retrouver les photos de la fête
    de fin d'année 2026 sans savoir qui les a déposées.
    """

    class Visibilite(models.TextChoices):
        GROUPE = "GROUPE", "Tout le groupe"
        FILIALE = "FILIALE", "La filiale seulement"
        SERVICE = "SERVICE", "Le service seulement"

    titre = models.CharField(
        verbose_name="Titre",
        max_length=200
    )

    description = models.TextField(
        verbose_name="Description",
        blank=True
    )

    filiale = models.ForeignKey(
        "filiales.Filiale",
        verbose_name="Filiale",
        on_delete=models.CASCADE,
        related_name="albums"
    )

    service = models.ForeignKey(
        "filiales.Service",
        verbose_name="Service",
        on_delete=models.SET_NULL,
        related_name="albums",
        null=True,
        blank=True
    )

    evenement = models.ForeignKey(
        "evenements.Evenement",
        verbose_name="Événement",
        on_delete=models.SET_NULL,
        related_name="albums",
        null=True,
        blank=True
    )

    visibilite = models.CharField(
        verbose_name="Visibilité",
        max_length=20,
        choices=Visibilite.choices,
        default=Visibilite.FILIALE
    )

    date_evenement = models.DateField(
        verbose_name="Date de l'événement",
        null=True,
        blank=True,
        help_text="Date à laquelle les photos ont été prises."
    )

    createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.PROTECT,
        related_name="albums_crees"
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
        verbose_name = "Album"
        verbose_name_plural = "Albums"
        ordering = ["-date_evenement", "-date_creation"]
        indexes = [
            models.Index(fields=["filiale", "-date_creation"]),
        ]

    def __str__(self):
        return self.titre

    def clean(self):
        if self.visibilite == self.Visibilite.SERVICE and not self.service_id:
            raise ValidationError({
                "service": "Une visibilité « service » impose de désigner le service.",
            })

        if self.service_id and self.filiale_id:
            if self.service.filiale_id != self.filiale_id:
                raise ValidationError({
                    "service": "Le service doit appartenir à la filiale de l'album.",
                })


def _chemin_photo(instance, nom_fichier):
    """Range les photos par album : media/galerie/<album>/<fichier>."""
    return f"galerie/{instance.album_id}/{nom_fichier}"


def _chemin_miniature(instance, nom_fichier):
    return f"galerie/{instance.album_id}/miniatures/{nom_fichier}"


class Photo(models.Model):
    """Une photo d'album, avec sa vignette générée au téléversement."""

    album = models.ForeignKey(
        "galerie.Album",
        verbose_name="Album",
        on_delete=models.CASCADE,
        related_name="photos"
    )

    image = models.ImageField(
        verbose_name="Image",
        upload_to=_chemin_photo,
        validators=[valider_taille_image],
        width_field="largeur",
        height_field="hauteur"
    )

    miniature = models.ImageField(
        verbose_name="Vignette",
        upload_to=_chemin_miniature,
        null=True,
        blank=True,
        editable=False
    )

    legende = models.CharField(
        verbose_name="Légende",
        max_length=255,
        blank=True
    )

    largeur = models.PositiveIntegerField(
        verbose_name="Largeur",
        null=True,
        blank=True,
        editable=False
    )

    hauteur = models.PositiveIntegerField(
        verbose_name="Hauteur",
        null=True,
        blank=True,
        editable=False
    )

    taille_octets = models.PositiveIntegerField(
        verbose_name="Taille (octets)",
        default=0,
        editable=False
    )

    televersee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Téléversée par",
        on_delete=models.PROTECT,
        related_name="photos_televersees"
    )

    date_creation = models.DateTimeField(
        verbose_name="Date de téléversement",
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Photo"
        verbose_name_plural = "Photos"
        ordering = ["date_creation"]
        indexes = [
            models.Index(fields=["album", "date_creation"]),
        ]

    def __str__(self):
        return self.legende or f"Photo {self.pk}"

    def save(self, *args, **kwargs):
        from .imagerie import generer_miniature

        if self.image and not self.taille_octets:
            self.taille_octets = self.image.size

        # La vignette se fabrique avant l'enregistrement : la générer après
        # imposerait un second save() et, avec lui, le risque de récursion.
        if self.image and not self.miniature:
            vignette = generer_miniature(self.image)
            if vignette is not None:
                self.miniature.save(vignette.name, vignette, save=False)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Supprime aussi les fichiers : sans cela, le volume conserverait
        indéfiniment des images que plus rien ne référence.
        """
        image, miniature = self.image, self.miniature
        resultat = super().delete(*args, **kwargs)

        for fichier in (image, miniature):
            if fichier:
                fichier.delete(save=False)

        return resultat
