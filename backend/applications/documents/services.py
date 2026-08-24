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
    toujours agir en plus, mais ne sont notifiés « à agir » que lorsque
    l'étape leur est explicitement destinée, pour éviter de les noyer de
    notifications routinières — ils reçoivent en revanche une notification
    de suivi sur chaque document, voir `_notifier_admins_suivi`).
    """
    role_requis = etape_config.get("role")
    if not role_requis:
        return User.objects.none()
    return User.objects.filter(filiale=document.filiale, role=role_requis, is_active=True)


def _notifier_admins_suivi(document, titre, message, exclure_ids=()):
    """
    L'administrateur voit passer chaque étape de chaque document, pour le
    suivi global — même quand ce n'est pas à lui d'agir dessus (EF-20 bis).
    """
    admins = User.objects.filter(role="ADMINISTRATEUR", is_active=True).exclude(pk__in=exclure_ids)
    for admin in admins:
        envoyer_notification(admin, titre, message, "INFO", objet=document)


def notifier_etape_courante(document, config):
    """
    Notifie les utilisateurs habilités à viser l'étape en cours — à appeler
    après la création d'un document, et après chaque visa qui fait avancer
    la chaîne sans la clôturer. Notifie aussi les administrateurs, pour
    suivi, qu'ils soient ou non habilités à viser cette étape.
    """
    if document.statut != Document.Statut.EN_COURS:
        return
    if document.etape_visa_courante >= len(config.visas):
        return

    etape = config.visas[document.etape_visa_courante]
    destinataires = list(_destinataires_etape(document, etape))
    for destinataire in destinataires:
        envoyer_notification(
            destinataire,
            f"{document.get_type_document_display()} en attente de votre visa",
            f"{document.numero} — {document.demandeur.nom_complet} — {etape.get('libelle')}",
            "INFO",
            objet=document,
        )

    exclure_ids = [document.demandeur_id] + [d.id for d in destinataires]
    _notifier_admins_suivi(
        document,
        f"Suivi — {document.get_type_document_display()}",
        f"{document.numero} ({document.demandeur.nom_complet}) — étape en cours : {etape.get('libelle')}.",
        exclure_ids=exclure_ids,
    )


def notifier_decision_finale(document, decision, commentaire=""):
    """Notifie le demandeur (et les administrateurs, pour suivi) de l'issue finale."""
    if decision == "REFUSE":
        envoyer_notification(
            document.demandeur,
            f"{document.get_type_document_display()} refusé",
            f"{document.numero} — {commentaire or 'Aucun motif renseigné.'}",
            "ERROR",
            objet=document,
        )
        titre_suivi = f"Suivi — {document.get_type_document_display()} refusé"
        message_suivi = f"{document.numero} ({document.demandeur.nom_complet}) a été refusé."
    else:
        envoyer_notification(
            document.demandeur,
            f"{document.get_type_document_display()} validé",
            f"{document.numero} a été entièrement validé.",
            "SUCCESS",
            objet=document,
        )
        titre_suivi = f"Suivi — {document.get_type_document_display()} validé"
        message_suivi = f"{document.numero} ({document.demandeur.nom_complet}) a été entièrement validé."

    _notifier_admins_suivi(document, titre_suivi, message_suivi, exclure_ids=[document.demandeur_id])


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
