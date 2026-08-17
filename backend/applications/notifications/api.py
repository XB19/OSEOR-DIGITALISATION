from django.utils import timezone
from rest_framework import viewsets, mixins, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin,
                          mixins.RetrieveModelMixin,
                          viewsets.GenericViewSet):
    """Notifications de l'utilisateur connecté (in-app)."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("lu", "type")
    ordering_fields = ("date_creation",)

    def get_queryset(self):
        return Notification.objects.filter(utilisateur=self.request.user)

    @action(detail=False, methods=["get"])
    def non_lues(self, request):
        return Response({"count": self.get_queryset().filter(lu=False).count()})

    @action(detail=True, methods=["post"])
    def marquer_lue(self, request, pk=None):
        notif = self.get_object()
        if not notif.lu:
            notif.lu = True
            notif.date_lecture = timezone.now()
            notif.save(update_fields=["lu", "date_lecture"])
        return Response(NotificationSerializer(notif).data)

    @action(detail=False, methods=["post"])
    def tout_marquer_lu(self, request):
        self.get_queryset().filter(lu=False).update(
            lu=True, date_lecture=timezone.now()
        )
        return Response({"detail": "Toutes les notifications sont marquées lues."})
