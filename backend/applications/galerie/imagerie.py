"""
Traitement des images téléversées : contrôle et vignettes.

Isolé du modèle pour rester testable seul — c'est le seul endroit du
projet qui manipule des fichiers binaires venus de l'extérieur.
"""

from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

from .models import DIMENSIONS_MAX, FORMATS_ACCEPTES, MINIATURE

#: Pillow refuse d'ouvrir au-delà, pour ne pas se faire saturer la mémoire
#: par une image-bombe. On garde une marge sur nos propres limites.
Image.MAX_IMAGE_PIXELS = DIMENSIONS_MAX[0] * DIMENSIONS_MAX[1]


def valider_image(fichier):
    """
    Vérifie que le fichier est bien une image d'un format accepté et de
    dimensions raisonnables.

    Ne se fie ni à l'extension ni au type MIME annoncé : les deux sont
    fournis par le client. Seul l'en-tête réel du fichier fait foi.
    """
    position = fichier.tell()
    fichier.seek(0)

    try:
        with Image.open(fichier) as image:
            format_image = image.format
            largeur, hauteur = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError(
            "Fichier illisible ou format d'image non reconnu."
        )
    finally:
        fichier.seek(position)

    if format_image not in FORMATS_ACCEPTES:
        raise ValidationError(
            f"Format {format_image} non accepté. "
            f"Formats admis : {', '.join(FORMATS_ACCEPTES)}."
        )

    if largeur > DIMENSIONS_MAX[0] or hauteur > DIMENSIONS_MAX[1]:
        raise ValidationError(
            f"Image trop grande ({largeur}x{hauteur}) : "
            f"{DIMENSIONS_MAX[0]}x{DIMENSIONS_MAX[1]} pixels maximum."
        )

    return format_image, (largeur, hauteur)


def generer_miniature(champ_image, taille=MINIATURE):
    """
    Fabrique une vignette JPEG à partir de l'image d'origine.

    Renvoie None si l'image est illisible : une vignette manquante dégrade
    l'affichage, elle ne doit pas empêcher le dépôt d'une photo.

    Les images à canal alpha (PNG, WEBP) sont aplaties sur fond blanc :
    JPEG ne sait pas représenter la transparence, et sans cela les zones
    transparentes ressortent en noir.
    """
    try:
        champ_image.open()
        with Image.open(champ_image) as image:
            image.load()

            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                fond = Image.new("RGB", image.size, (255, 255, 255))
                fond.paste(image, mask=image.split()[-1])
                image = fond
            elif image.mode != "RGB":
                image = image.convert("RGB")

            image.thumbnail(taille, Image.Resampling.LANCZOS)

            tampon = BytesIO()
            image.save(tampon, format="JPEG", quality=82, optimize=True)

    except (UnidentifiedImageError, OSError, ValueError,
            Image.DecompressionBombError):
        return None
    finally:
        try:
            champ_image.seek(0)
        except (ValueError, OSError):
            pass

    nom = Path(getattr(champ_image, "name", "photo")).stem or "photo"
    return ContentFile(tampon.getvalue(), name=f"{nom}_vignette.jpg")
