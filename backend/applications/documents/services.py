from django.contrib.auth import get_user_model

from applications.notifications.services import envoyer_notification
from .models import Document

User = get_user_model()


def _destinataires_etape(document, etape_config):
    """
    Utilisateurs habilités à viser l'étape donnée : ceux du rôle requis,
    dans la filiale du document (le Directeur/Administrateur peuvent
    toujours agir en plus, mais ne sont notifiés que lorsque l'étape leur
    est explicitement destinée, pour éviter de les noyer de notifications
    routinières).
    """
    role_requis = etape_config.get("role")
    if not role_requis:
        return User.objects.none()
    return User.objects.filter(filiale=document.filiale, role=role_requis, is_active=True)


def notifier_etape_courante(document, config):
    """
    Notifie les utilisateurs habilités à viser l'étape en cours — à appeler
    après la création d'un document, et après chaque visa qui fait avancer
    la chaîne sans la clôturer.
    """
    if document.statut != Document.Statut.EN_COURS:
        return
    if document.etape_visa_courante >= len(config.visas):
        return

    etape = config.visas[document.etape_visa_courante]
    for destinataire in _destinataires_etape(document, etape):
        envoyer_notification(
            destinataire,
            f"{document.get_type_document_display()} en attente de votre visa",
            f"{document.numero} — {document.demandeur.nom_complet} — {etape.get('libelle')}",
            "INFO",
            objet=document,
        )


def notifier_decision_finale(document, decision, commentaire=""):
    """Notifie le demandeur quand son document est entièrement validé ou refusé."""
    if decision == "REFUSE":
        envoyer_notification(
            document.demandeur,
            f"{document.get_type_document_display()} refusé",
            f"{document.numero} — {commentaire or 'Aucun motif renseigné.'}",
            "ERROR",
            objet=document,
        )
    else:
        envoyer_notification(
            document.demandeur,
            f"{document.get_type_document_display()} validé",
            f"{document.numero} a été entièrement validé.",
            "SUCCESS",
            objet=document,
        )
