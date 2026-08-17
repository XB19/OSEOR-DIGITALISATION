from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification


def envoyer_notification(utilisateur, titre, message, type_notification="INFO", objet=None):
    """
    Crée une notification in-app et la pousse en temps réel via WebSocket
    (EF-18 / RG-12). L'envoi e-mail est géré en parallèle par le caller
    ou un signal (backend console en dev).

    - objet : instance de modèle concernée (Reservation, Audience,
      Document…), optionnelle — permet au clic sur la notification
      d'ouvrir directement l'élément à traiter (même pattern que
      `enregistrer_action` côté journal d'audit).
    """

    notification = Notification.objects.create(
        utilisateur=utilisateur,
        titre=titre,
        message=message,
        type=type_notification,
        objet_type=objet.__class__.__name__ if objet is not None else "",
        objet_id=getattr(objet, "pk", None) if objet is not None else None,
    )

    _pousser_temps_reel(notification)
    _envoyer_email(utilisateur, titre, message)
    return notification


def _envoyer_email(utilisateur, titre, message):
    """Envoi e-mail best-effort (console en dev, Office 365 en prod)."""
    email = getattr(utilisateur, "email", "")
    if not email:
        return
    try:
        from django.conf import settings
        from django.core.mail import send_mail

        send_mail(
            subject=f"[OSEOR] {titre}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        pass


def _pousser_temps_reel(notification):
    """Pousse la notification sur le groupe WebSocket de l'utilisateur."""
    layer = get_channel_layer()
    if layer is None:
        return
    contenu = {
        "id": notification.id,
        "titre": notification.titre,
        "message": notification.message,
        "type": notification.type,
        "lu": notification.lu,
        "objet_type": notification.objet_type,
        "objet_id": notification.objet_id,
        "date_creation": notification.date_creation.isoformat(),
    }
    try:
        async_to_sync(layer.group_send)(
            f"notifs_{notification.utilisateur_id}",
            {"type": "notifier", "contenu": contenu},
        )
    except Exception:
        # Le temps réel ne doit jamais bloquer la création de la notification.
        pass
