"""
Exécution d'un circuit de validation : consigner une décision, prévenir
l'étape suivante, informer les observateurs.

Le module métier garde la maîtrise de son état (statut, conséquences
comptables). Ce module ne fait que trois choses, mais les fait une seule
fois pour tout le monde : vérifier l'habilitation, écrire la trace, et
avertir les bonnes personnes.
"""

from django.contrib.auth import get_user_model

from applications.notifications.services import envoyer_notification

from .circuits import etapes_sautees, peut_agir, resoudre_acteurs
from .models import DecisionValidation

User = get_user_model()


class ValidationRefusee(Exception):
    """Règle de circuit violée ; le message est destiné à l'utilisateur."""


def decisions(objet):
    """Historique des décisions prises sur cet objet, dans l'ordre."""
    return DecisionValidation.objects.filter(
        objet_type=objet.__class__.__name__, objet_id=objet.pk,
    ).select_related("acteur")


def enregistrer_decision(objet, circuit, index, acteur, demandeur,
                         approuvee, commentaire=""):
    """
    Consigne une décision après avoir vérifié l'habilitation.

    Renvoie le couple (décision, index de l'étape suivante). L'index
    renvoyé tient compte des étapes sautées par une validation directe :
    c'est au module métier de conclure si le circuit est terminé.

    Lève `ValidationRefusee` si l'acteur n'est pas habilité — le contrôle
    vit ici pour ne pas être réécrit, et mal, dans chaque module.
    """
    etape = circuit.etape(index)
    if etape is None:
        raise ValidationRefusee("Ce circuit est déjà terminé.")

    if not peut_agir(circuit, index, acteur, demandeur, objet):
        raise ValidationRefusee(
            "Vous n'êtes pas habilité à trancher cette étape.")

    sautees = etapes_sautees(circuit, index, acteur, demandeur, objet)

    decision = DecisionValidation.objects.create(
        objet_type=objet.__class__.__name__,
        objet_id=objet.pk,
        etape_cle=etape.cle,
        etape_libelle=etape.libelle,
        ordre=index,
        acteur=acteur,
        sens=(DecisionValidation.Sens.VALIDEE if approuvee
              else DecisionValidation.Sens.REFUSEE),
        validation_directe=bool(sautees),
        etapes_sautees=sautees,
        commentaire=commentaire,
    )

    if not approuvee:
        # Un refus clôt le circuit : rien ne sert d'avancer.
        return decision, len(circuit)

    # Une validation directe consomme aussi les étapes qu'elle a sautées.
    return decision, index + len(sautees) + 1


def notifier_etape(objet, circuit, index, demandeur, titre, message,
                   type_notification="INFO"):
    """Prévient les acteurs de l'étape courante qu'une décision les attend."""
    etape = circuit.etape(index)
    if etape is None:
        return 0

    identifiants = resoudre_acteurs(etape, demandeur, objet)
    if not identifiants:
        return 0

    envoyees = 0
    for destinataire in User.objects.filter(pk__in=identifiants, is_active=True):
        envoyer_notification(
            destinataire, titre, message, type_notification, objet=objet)
        envoyees += 1
    return envoyees


def notifier_observateurs(objet, circuit, titre, message,
                          type_notification="INFO", filiale_id=None,
                          exclure=()):
    """
    Informe les rôles observateurs du circuit.

    Ils sont tenus au courant sans jamais être sollicités : les RH et la
    comptabilité doivent savoir qui s'absente et quand, sans devoir
    approuver quoi que ce soit.
    """
    if not circuit.observateurs:
        return 0

    destinataires = User.objects.filter(
        is_active=True, role__in=circuit.observateurs)

    if filiale_id is not None:
        destinataires = destinataires.filter(filiale_id=filiale_id)

    exclus = {getattr(u, "pk", u) for u in exclure if u is not None}

    envoyees = 0
    for destinataire in destinataires:
        if destinataire.pk in exclus:
            continue
        envoyer_notification(
            destinataire, titre, message, type_notification, objet=objet)
        envoyees += 1
    return envoyees
