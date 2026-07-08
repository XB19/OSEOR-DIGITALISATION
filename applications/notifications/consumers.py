import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Canal temps réel des notifications d'un utilisateur (EF-18).

    Chaque utilisateur authentifié rejoint le groupe `notifs_<id>`.
    Le service `envoyer_notification` pousse les nouvelles notifications
    sur ce groupe.
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close()
            return
        self.group_name = f"notifs_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notifier(self, event):
        """Reçoit un message du groupe et le transmet au client WebSocket."""
        await self.send(text_data=json.dumps(event["contenu"]))
