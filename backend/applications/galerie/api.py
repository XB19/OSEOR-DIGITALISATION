from rest_framework import viewsets, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from applications.journalisation.services import enregistrer_action

from .models import Album, Photo
from .serializers import AlbumEcritureSerializer, AlbumSerializer, PhotoSerializer
from . import services


class AlbumViewSet(viewsets.ModelViewSet):
    """
    Albums photo de la vie du groupe.

    Consultation selon la visibilité de l'album ; seuls son créateur et la
    direction le modifient ou le suppriment.
    """

    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("filiale", "service", "evenement", "visibilite")
    search_fields = ("titre", "description")
    ordering_fields = ("date_evenement", "date_creation", "titre")

    def get_queryset(self):
        return services.albums_visibles(self.request.user)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return AlbumEcritureSerializer
        return AlbumSerializer

    def _refus(self):
        return Response(
            {"detail": "Seuls le créateur de l'album et la direction peuvent "
                       "le modifier."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def perform_create(self, serializer):
        album = serializer.save(createur=self.request.user)
        enregistrer_action(
            self.request.user, "ALBUM_CREE", album.titre, objet=album)

    def update(self, request, *args, **kwargs):
        if not services.peut_gerer_album(self.get_object(), request.user):
            return self._refus()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        album = self.get_object()
        if not services.peut_gerer_album(album, request.user):
            return self._refus()

        # Les fichiers partent avec les photos : la suppression en cascade
        # côté base n'appelle pas Photo.delete(), qui nettoie le disque.
        for photo in album.photos.all():
            photo.delete()

        enregistrer_action(
            request.user, "ALBUM_SUPPRIME", album.titre, objet=album)
        return super().destroy(request, *args, **kwargs)


class PhotoViewSet(viewsets.ModelViewSet):
    """
    Photos d'un album.

    Tout membre voyant l'album peut y déposer une photo ; seuls l'auteur du
    dépôt, le propriétaire de l'album et la direction peuvent la retirer —
    une galerie d'entreprise n'est pas un mur ouvert.
    """

    serializer_class = PhotoSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ("album",)
    ordering_fields = ("date_creation",)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        albums = services.albums_visibles(self.request.user)
        return Photo.objects.filter(album__in=albums).select_related(
            "album", "televersee_par")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        album = serializer.validated_data["album"]
        if not services.albums_visibles(request.user).filter(pk=album.pk).exists():
            return Response(
                {"detail": "Cet album ne vous est pas accessible."},
                status=status.HTTP_403_FORBIDDEN,
            )

        photo = serializer.save(televersee_par=request.user)
        enregistrer_action(
            request.user, "PHOTO_AJOUTEE",
            f"{album.titre} — {photo.legende or photo.image.name}", objet=photo)

        return Response(
            self.get_serializer(photo).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """Seule la légende se modifie ; l'image, elle, se remplace."""
        photo = self.get_object()
        if not services.peut_supprimer_photo(photo, request.user):
            return Response(
                {"detail": "Vous ne pouvez pas modifier cette photo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        photo.legende = request.data.get("legende", photo.legende)
        photo.save(update_fields=["legende"])
        return Response(self.get_serializer(photo).data)

    def destroy(self, request, *args, **kwargs):
        photo = self.get_object()

        if not services.peut_supprimer_photo(photo, request.user):
            return Response(
                {"detail": "Seuls l'auteur du dépôt, le propriétaire de "
                           "l'album et la direction peuvent retirer cette photo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        enregistrer_action(
            request.user, "PHOTO_SUPPRIMEE",
            f"{photo.album.titre} — {photo.legende or photo.pk}", objet=photo)

        # Passe par Photo.delete(), qui efface aussi les fichiers.
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
