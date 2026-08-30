"""
Vie d'un congé après sa validation : report, rappel en service, reprise,
renoncement au reliquat.

Deux règles de l'article 44 de la Convention Collective structurent tout
ce module :

**b — Organisation du congé.** « Cette date étant fixée, le départ ne
pourra être avancé ni retardé d'une durée supplémentaire supérieure à
trois mois. » Un report est donc licite, mais plafonné, et se compte
depuis la date **initialement** fixée — sans quoi trois reports d'un mois
contourneraient la limite.

**d — Rappel.** « Si pour des raisons de service le travailleur en congé
est rappelé, son congé sera prolongé des jours ainsi travaillés. » Les
jours travaillés pendant le congé lui sont donc **rendus** : c'est un
droit, pas une faveur. Le salarié peut y renoncer et reprendre le travail
définitivement, mais ce renoncement doit être un choix consigné, jamais un
effet de bord silencieux.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from applications.journalisation.services import enregistrer_action
from applications.notifications.services import envoyer_notification
from config.permissions import RH, est_direction

from . import services
from .calendrier import compter_jours_ouvres, jours_ouvres
from .models import DemandeConge, MouvementConge
from .workflow import DemandeRefusee, _informer_observateurs

#: Plafond de report, article 44b de la CCIT.
REPORT_MAX_MOIS = 3


def _peut_administrer(demande, utilisateur):
    """
    Qui agit sur un congé déjà validé : la direction, les RH, et le
    responsable qui l'a accordé. Pas le salarié — on ne se rappelle pas
    soi-même, et on ne décale pas son propre départ sans accord.
    """
    if est_direction(utilisateur) or utilisateur.role == RH:
        return True
    return utilisateur.pk in {
        getattr(demande.valideur, "pk", None),
        getattr(demande.utilisateur.responsable_hierarchique, "pk", None),
    }


def _plafond_report(demande):
    """Date au-delà de laquelle un report dépasserait les trois mois."""
    origine = demande.date_debut_initiale or demande.date_debut
    mois = origine.month - 1 + REPORT_MAX_MOIS
    annee = origine.year + mois // 12
    mois = mois % 12 + 1
    # Un 31 mai reporté de trois mois vise le 31 août ; si le mois cible est
    # plus court, on retient son dernier jour.
    from calendar import monthrange

    return date(annee, mois, min(origine.day, monthrange(annee, mois)[1]))


# =====================================================================
# Report du départ
# =====================================================================

def reporter(demande, nouvelle_date_debut, acteur, motif=""):
    """
    Décale le départ en congé, en conservant la durée demandée.

    Le cas visé par la direction : « nous avons encore besoin de vous ».
    La durée est préservée — on décale la fenêtre, on ne raccourcit pas le
    droit — et le solde est réajusté si le nouveau calendrier ne contient
    pas le même nombre de jours ouvrés (un report peut enjamber un férié).
    """
    if demande.statut not in (DemandeConge.Statut.EN_ATTENTE,
                              DemandeConge.Statut.VALIDEE):
        raise DemandeRefusee(
            "Seul un congé en attente ou validé peut être reporté.")

    if not _peut_administrer(demande, acteur):
        raise DemandeRefusee("Vous ne pouvez pas reporter ce congé.")

    if not motif.strip():
        raise DemandeRefusee(
            "Un report doit être motivé : le salarié doit savoir pourquoi "
            "son départ est décalé.")

    origine = demande.date_debut_initiale or demande.date_debut
    if nouvelle_date_debut < origine:
        raise DemandeRefusee(
            "Un report décale le départ ; il ne l'avance pas.")

    plafond = _plafond_report(demande)
    if nouvelle_date_debut > plafond:
        raise DemandeRefusee(
            f"L'article 44 de la Convention Collective limite le report à "
            f"{REPORT_MAX_MOIS} mois : au plus tard le "
            f"{plafond:%d/%m/%Y}.")

    duree = demande.date_fin - demande.date_debut
    nouvelle_fin = nouvelle_date_debut + duree

    filiale = demande.filiale_salarie
    nouveaux_jours = compter_jours_ouvres(
        nouvelle_date_debut, nouvelle_fin, filiale)

    if nouveaux_jours == 0:
        raise DemandeRefusee(
            "La période visée ne contient aucun jour ouvré.")

    with transaction.atomic():
        if demande.date_debut_initiale is None:
            demande.date_debut_initiale = demande.date_debut

        ancien_debut = demande.date_debut
        demande.date_debut = nouvelle_date_debut
        demande.date_fin = nouvelle_fin
        demande.motif_report = motif

        ancien_decompte = demande.jours_ouvres
        demande.jours_ouvres = nouveaux_jours
        demande.save()

        # Le solde suit le calendrier réel : un report qui enjambe un férié
        # ne doit pas coûter un jour de plus au salarié.
        if demande.statut == DemandeConge.Statut.VALIDEE:
            _ajuster_consommation(
                demande, ancien_decompte, nouveaux_jours,
                f"Report du {ancien_debut:%d/%m/%Y} au "
                f"{nouvelle_date_debut:%d/%m/%Y}")

        enregistrer_action(
            acteur, "CONGE_REPORTE",
            f"{demande.utilisateur.nom_complet} — {ancien_debut:%d/%m/%Y} → "
            f"{nouvelle_date_debut:%d/%m/%Y}", objet=demande)

    envoyer_notification(
        demande.utilisateur,
        "Congé reporté",
        f"Votre départ est décalé au {nouvelle_date_debut:%d/%m/%Y} "
        f"(retour le {nouvelle_fin:%d/%m/%Y}) — {motif}",
        "WARNING",
        objet=demande,
    )
    _informer_observateurs(demande, "Congé reporté", "WARNING")

    return demande


# =====================================================================
# Rappel en service
# =====================================================================

def rappeler(demande, acteur, motif="", jour=None):
    """
    Rappelle un salarié pendant son congé.

    Le congé passe en INTERROMPUE : il n'est ni terminé ni annulé, il
    attend que le salarié reprenne son congé ou y renonce. Tant que ce
    choix n'est pas fait, le solde reste débité — c'est la reprise ou le
    renoncement qui le rectifie.
    """
    jour = jour or timezone.localdate()

    if demande.statut != DemandeConge.Statut.VALIDEE:
        raise DemandeRefusee("Seul un congé validé peut être interrompu.")

    if not _peut_administrer(demande, acteur):
        raise DemandeRefusee("Vous ne pouvez pas rappeler ce salarié.")

    if not motif.strip():
        raise DemandeRefusee("Un rappel doit être motivé.")

    if jour < demande.date_debut or jour > demande.date_fin:
        raise DemandeRefusee(
            f"Le rappel doit tomber pendant le congé "
            f"({demande.date_debut:%d/%m/%Y} au {demande.date_fin:%d/%m/%Y}).")

    with transaction.atomic():
        demande.statut = DemandeConge.Statut.INTERROMPUE
        demande.date_rappel = jour
        demande.motif_rappel = motif
        demande.rappele_par = acteur
        demande.save()

        enregistrer_action(
            acteur, "CONGE_RAPPEL",
            f"{demande.utilisateur.nom_complet} — rappelé le {jour:%d/%m/%Y}",
            objet=demande)

    envoyer_notification(
        demande.utilisateur,
        "Rappel en service",
        f"Vous êtes rappelé le {jour:%d/%m/%Y} — {motif}. Vos jours de congé "
        f"travaillés vous seront rendus.",
        "WARNING",
        objet=demande,
    )
    _informer_observateurs(demande, "Congé interrompu (rappel)", "WARNING")

    return demande


def reprendre(demande, acteur, jour=None):
    """
    Le salarié repart en congé après son rappel.

    Conformément à l'article 44d, le congé est **prolongé** du nombre de
    jours ouvrés travaillés pendant l'interruption : le salarié retrouve
    les jours qu'on lui a pris. Le nombre de jours consommés ne change
    donc pas — seule la date de retour recule.
    """
    jour = jour or timezone.localdate()

    if demande.statut != DemandeConge.Statut.INTERROMPUE:
        raise DemandeRefusee("Ce congé n'est pas interrompu.")

    if not (_peut_administrer(demande, acteur)
            or acteur.pk == demande.utilisateur_id):
        raise DemandeRefusee("Vous ne pouvez pas agir sur ce congé.")

    if jour < demande.date_rappel:
        raise DemandeRefusee(
            "La reprise ne peut pas précéder le rappel.")

    filiale = demande.filiale_salarie
    travailles = compter_jours_ouvres(demande.date_rappel, jour, filiale)

    with transaction.atomic():
        demande.date_reprise = jour
        demande.statut = DemandeConge.Statut.VALIDEE

        # Prolonger de `travailles` jours OUVRÉS : on avance la date de fin
        # jour après jour jusqu'à en avoir rendu autant.
        demande.date_fin = _prolonger(demande.date_fin, travailles, filiale)
        demande.save()

        enregistrer_action(
            acteur, "CONGE_REPRISE",
            f"{demande.utilisateur.nom_complet} — reprise du congé le "
            f"{jour:%d/%m/%Y}, prolongé de {travailles} j",
            objet=demande)

    envoyer_notification(
        demande.utilisateur,
        "Congé prolongé",
        f"Vos {travailles} jour(s) travaillés pendant le rappel vous sont "
        f"rendus : retour prévu le {demande.date_fin:%d/%m/%Y}.",
        "SUCCESS",
        objet=demande,
    )
    _informer_observateurs(demande, "Congé repris", "INFO")

    return demande


def renoncer_au_reliquat(demande, acteur, jour=None):
    """
    Le salarié renonce à la fin de son congé et reprend le travail.

    Les jours non pris lui sont recrédités : il ne doit pas les perdre pour
    avoir répondu à un rappel. Le renoncement est un choix explicite — la
    prolongation de l'article 44d reste le droit par défaut.
    """
    jour = jour or timezone.localdate()

    if demande.statut not in (DemandeConge.Statut.INTERROMPUE,
                              DemandeConge.Statut.VALIDEE):
        raise DemandeRefusee(
            "Seul un congé en cours ou interrompu peut être écourté.")

    if not (_peut_administrer(demande, acteur)
            or acteur.pk == demande.utilisateur_id):
        raise DemandeRefusee("Vous ne pouvez pas agir sur ce congé.")

    filiale = demande.filiale_salarie
    fin_effective = demande.date_rappel or jour

    # Jours réellement passés en congé, avant l'interruption.
    if fin_effective <= demande.date_debut:
        jours_pris = 0
    else:
        jours_pris = compter_jours_ouvres(
            demande.date_debut, fin_effective - timedelta(days=1), filiale)

    with transaction.atomic():
        ancien_decompte = demande.jours_ouvres

        demande.date_fin = max(
            demande.date_debut, fin_effective - timedelta(days=1))
        demande.jours_ouvres = jours_pris
        demande.statut = DemandeConge.Statut.TERMINEE
        demande.save()

        _ajuster_consommation(
            demande, ancien_decompte, jours_pris,
            "Renoncement au reliquat après rappel")

        enregistrer_action(
            acteur, "CONGE_ECOURTE",
            f"{demande.utilisateur.nom_complet} — {ancien_decompte} j → "
            f"{jours_pris} j", objet=demande)

    rendus = ancien_decompte - jours_pris
    if rendus > 0:
        envoyer_notification(
            demande.utilisateur,
            "Congé écourté",
            f"{rendus} jour(s) non pris vous ont été recrédités.",
            "SUCCESS",
            objet=demande,
        )
    _informer_observateurs(demande, "Congé écourté", "INFO")

    return demande


# =====================================================================
# Outils
# =====================================================================

def _prolonger(fin, jours_a_rendre, filiale):
    """Recule `fin` de `jours_a_rendre` jours OUVRÉS."""
    if jours_a_rendre <= 0:
        return fin

    courant = fin
    rendus = 0
    while rendus < jours_a_rendre:
        courant += timedelta(days=1)
        if jours_ouvres(courant, courant, filiale):
            rendus += 1
    return courant


def _ajuster_consommation(demande, ancien, nouveau, motif):
    """
    Écrit au registre l'écart entre l'ancien et le nouveau décompte.

    Une correction s'ajoute, elle ne réécrit pas l'écriture d'origine : le
    salarié doit pouvoir suivre, ligne à ligne, d'où vient son solde.
    """
    if not demande.decompte_le_solde:
        return None

    ecart = ancien - nouveau
    if ecart == 0:
        return None

    return MouvementConge.objects.create(
        utilisateur=demande.utilisateur,
        annee=demande.date_debut.year,
        type_mouvement=MouvementConge.TypeMouvement.CORRECTION,
        jours=Decimal(ecart),
        date_effet=timezone.localdate(),
        demande=demande,
        motif=motif,
    )
