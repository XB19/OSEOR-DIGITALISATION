from rest_framework import mixins, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from applications.documents.models import Document, TypeDocument
from applications.journalisation.services import enregistrer_action
from config.permissions import est_direction

from .models import LectureNote
from .serializers import LectureNoteSerializer
from . import services


class NoteRecueViewSet(mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       viewsets.GenericViewSet):
    """
    Notes internes adressées à l'utilisateur connecté, avec leur accusé de
    lecture.

    Lecture seule : une note se rédige comme n'importe quel document
    (`POST /api/documents/` avec type_document=NOTE_INTERNE) et se diffuse
    toute seule une fois signée par la direction.
    """

    serializer_class = LectureNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("note",)
    ordering_fields = ("date_diffusion", "date_lecture")

    def get_queryset(self):
        queryset = LectureNote.objects.filter(
            destinataire=self.request.user,
        ).select_related("note", "note__filiale", "note__demandeur")

        if self.request.query_params.get("non_lues") == "1":
            queryset = queryset.filter(date_lecture__isnull=True)

        return queryset

    @action(detail=True, methods=["post"])
    def marquer_lue(self, request, pk=None):
        """Accuse réception de la note."""
        lecture = self.get_object()

        deja_lue = lecture.lue
        services.marquer_lue(lecture.note, request.user)
        lecture.refresh_from_db()

        if not deja_lue:
            enregistrer_action(
                request.user, "NOTE_LUE", lecture.note.numero, objet=lecture.note)

        return Response(self.get_serializer(lecture).data)

    @action(detail=False, methods=["get"])
    def diffusion(self, request):
        """
        Avancement de la prise de connaissance d'une note — réservé à son
        rédacteur et à la direction : c'est eux que « qui n'a pas encore lu »
        concerne.

        Paramètre `note` : identifiant de la note.
        """
        identifiant = request.query_params.get("note")
        if not identifiant:
            return Response({"detail": "Paramètre note requis."}, status=400)

        note = Document.objects.filter(
            pk=identifiant, type_document=TypeDocument.NOTE_INTERNE).first()
        if note is None:
            return Response({"detail": "Note introuvable."}, status=404)

        if not (est_direction(request.user) or note.demandeur_id == request.user.pk):
            return Response(
                {"detail": "Seuls le rédacteur et la direction peuvent consulter "
                           "le suivi de diffusion."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(services.statistiques_diffusion(note))
