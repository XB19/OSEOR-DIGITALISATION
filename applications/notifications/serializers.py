from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "titre",
            "message",
            "type",
            "lu",
            "date_creation",
            "date_lecture",
        )
        read_only_fields = fields
