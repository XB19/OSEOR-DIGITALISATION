"""
Diffusion automatique d'une note interne dès qu'elle est signée.

Passer par un signal plutôt que par un appel dans `documents/api.py` est
délibéré : le moteur documentaire n'a pas à connaître les notes internes,
et le module Notes reste greffable sans toucher au code partagé — sur
lequel travaille aussi le module d'export PDF.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from applications.documents.models import Document, TypeDocument


@receiver(post_save, sender=Document, dispatch_uid="notes_diffuser_note_signee")
def diffuser_note_signee(sender, instance, **kwargs):
    if instance.type_document != TypeDocument.NOTE_INTERNE:
        return
    if instance.statut != Document.Statut.VALIDE:
        return

    # Import tardif : `services` importe les modèles, qui importent ce
    # module au chargement de l'application.
    from .services import diffuser

    diffuser(instance)
