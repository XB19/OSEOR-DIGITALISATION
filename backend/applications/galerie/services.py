"""Périmètre de visibilité des albums, aligné sur celui des événements."""

from django.db.models import Count, Q

from config.permissions import est_direction

from .models import Album


def albums_visibles(utilisateur):
    """
    Albums que `utilisateur` peut consulter :

    - direction : tout le groupe ;
    - visibilité GROUPE : tout le monde ;
    - visibilité FILIALE : les membres de la filiale ;
    - visibilité SERVICE : les membres du service.

    Même vocabulaire que les événements et les notes internes : trois
    modules qui répondent à la même question ne doivent pas y répondre de
    trois façons différentes.
    """
    queryset = Album.objects.select_related(
        "filiale", "service", "evenement", "createur",
    ).annotate(nb_photos=Count("photos"))

    if est_direction(utilisateur):
        return queryset

    if not (utilisateur and utilisateur.is_authenticated):
        return queryset.none()

    perimetre = Q(visibilite=Album.Visibilite.GROUPE)

    if getattr(utilisateur, "filiale_id", None) is not None:
        perimetre |= Q(
            visibilite=Album.Visibilite.FILIALE,
            filiale_id=utilisateur.filiale_id,
        )

    if getattr(utilisateur, "service_id", None) is not None:
        perimetre |= Q(
            visibilite=Album.Visibilite.SERVICE,
            service_id=utilisateur.service_id,
        )

    return queryset.filter(perimetre)


def peut_gerer_album(album, utilisateur):
    """Qui modifie ou supprime un album : son créateur et la direction."""
    return est_direction(utilisateur) or album.createur_id == utilisateur.pk


def peut_supprimer_photo(photo, utilisateur):
    """
    Qui retire une photo : celui qui l'a déposée, le propriétaire de
    l'album, et la direction.

    Point volontaire : on ne laisse pas n'importe quel collègue effacer la
    photo d'un autre — c'est une galerie d'entreprise, pas un mur ouvert.
    """
    if est_direction(utilisateur):
        return True
    if photo.televersee_par_id == utilisateur.pk:
        return True
    return photo.album.createur_id == utilisateur.pk
