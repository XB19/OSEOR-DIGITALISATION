from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

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


def rappeler_documents_en_attente(seuil_jours=3):
    """
    Relance les visas dormants : tout document encore EN_COURS qui n'a pas
    bougé depuis `seuil_jours` renotifie les personnes habilitées à viser
    son étape courante.

    C'est le point faible du zéro-papier : une fiche papier posée sur un
    bureau finit par se voir, un document en base attend indéfiniment que
    quelqu'un pense à ouvrir la page. Renvoyé par la tâche planifiée
    correspondante.

    Idempotente : ne modifie aucun document, se contente de renotifier.
    Relancer la tâche deux fois n'envoie que des notifications en double,
    jamais de corruption d'état.
    """
    limite = timezone.now() - timedelta(days=seuil_jours)

    documents = (
        Document.objects
        .filter(statut=Document.Statut.EN_COURS, date_modification__lt=limite)
        .select_related("filiale", "demandeur")
    )

    relances = 0
    for document in documents:
        config = document.configuration()
        if not config or not config.visas:
            continue
        notifier_etape_courante(document, config)
        relances += 1

    return relances
