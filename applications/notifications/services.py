from .models import Notification


def envoyer_notification(utilisateur, titre, message, type_notification="INFO"):
    """
    Crée une notification pour un utilisateur.
    """

    return Notification.objects.create(
        utilisateur=utilisateur,
        titre=titre,
        message=message,
        type=type_notification
    )