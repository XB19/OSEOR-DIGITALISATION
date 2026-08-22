"""
Diffusion des notes internes.

Une note interne est un `Document` de type NOTE_INTERNE : elle réutilise la
numérotation, la chaîne de visas et le journal d'audit du moteur
documentaire. Ce module ajoute ce que le moteur ne sait pas faire — porter
la note jusqu'à ses destinataires, et savoir qui l'a lue.

Le périmètre de diffusion est stocké dans `champs_entete["visibilite"]`,
avec le même vocabulaire que les événements : GROUPE, FILIALE, SERVICE.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from applications.documents.models import Document, TypeDocument

from .models import LectureNote

User = get_user_model()

GROUPE = "GROUPE"
FILIALE = "FILIALE"
SERVICE = "SERVICE"

#: Périmètre retenu quand la note n'en précise aucun. Le plus restrictif
#: des trois : une note ne part jamais à tout le groupe par inadvertance.
VISIBILITE_PAR_DEFAUT = FILIALE


def destinataires(note):
    """
    Utilisateurs actifs visés par la note, son rédacteur exclu — il n'a pas
    à s'accuser réception de sa propre note.
    """
    entete = note.champs_entete or {}
    visibilite = entete.get("visibilite", VISIBILITE_PAR_DEFAUT)

    personnes = User.objects.filter(is_active=True)

    if visibilite == GROUPE:
        pass
    elif visibilite == SERVICE:
        service_id = entete.get("service_id")
        if not service_id:
            return User.objects.none()
        personnes = personnes.filter(service_id=service_id)
    else:
        personnes = personnes.filter(filiale_id=note.filiale_id)

    return personnes.exclude(pk=note.demandeur_id)


def diffuser(note):
    """
    Crée la liste de diffusion de la note et prévient ses destinataires.

    Idempotente : relancée, elle ne recrée pas les lignes existantes et ne
    renotifie personne. C'est indispensable — la diffusion est déclenchée
    par un signal sur la sauvegarde du document, qui peut se déclencher
    plusieurs fois pour une même note.

    Renvoie le nombre de destinataires nouvellement ajoutés.
    """
    from applications.notifications.services import envoyer_notification

    if note.type_document != TypeDocument.NOTE_INTERNE:
        return 0
    if note.statut != Document.Statut.VALIDE:
        return 0

    deja_destinataires = set(
        LectureNote.objects.filter(note=note).values_list(
            "destinataire_id", flat=True)
    )

    nouveaux = [
        personne for personne in destinataires(note)
        if personne.pk not in deja_destinataires
    ]
    if not nouveaux:
        return 0

    with transaction.atomic():
        LectureNote.objects.bulk_create(
            [LectureNote(note=note, destinataire=personne) for personne in nouveaux],
            ignore_conflicts=True,
        )

    entete = note.champs_entete or {}
    objet = entete.get("objet") or note.numero

    for personne in nouveaux:
        envoyer_notification(
            personne,
            "Nouvelle note interne",
            f"{note.numero} — {objet}",
            "INFO",
            objet=note,
        )

    return len(nouveaux)


def marquer_lue(note, utilisateur):
    """
    Enregistre l'accusé de lecture. Ne réécrit pas une date déjà posée :
    c'est la PREMIÈRE lecture qui fait foi.

    Renvoie la ligne de lecture, ou None si l'utilisateur n'est pas
    destinataire de cette note.
    """
    lecture = LectureNote.objects.filter(
        note=note, destinataire=utilisateur).first()

    if lecture is None:
        return None

    if lecture.date_lecture is None:
        lecture.date_lecture = timezone.now()
        lecture.save(update_fields=["date_lecture"])

    return lecture


def statistiques_diffusion(note):
    """Avancement de la prise de connaissance d'une note."""
    lectures = LectureNote.objects.filter(note=note).select_related("destinataire")

    lues = [l for l in lectures if l.date_lecture is not None]
    non_lues = [l for l in lectures if l.date_lecture is None]

    return {
        "destinataires": len(lectures),
        "lues": len(lues),
        "non_lues": len(non_lues),
        "en_attente": [
            {
                "utilisateur_id": l.destinataire_id,
                "nom": l.destinataire.nom_complet,
            }
            for l in non_lues
        ],
    }
