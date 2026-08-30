"""
Mouvements de caisse et parcours d'un bon de sortie.

Toute écriture passe par ici : le solde étant la somme du registre, écrire
ailleurs reviendrait à fausser le solde sans laisser de trace.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from applications.journalisation.services import enregistrer_action
from applications.notifications.services import envoyer_notification
from applications.validation import services as validation
from applications.validation.services import ValidationRefusee
from config.permissions import est_direction

from .circuits import (
    CIRCUIT_BON_SORTIE, destinataire_acceptable, roles_autorises,
    seuil_direction,
)
from .models import BonSortie, Caisse, MouvementCaisse


class OperationRefusee(Exception):
    """Règle de caisse violée ; le message est destiné à l'utilisateur."""


# =====================================================================
# Habilitations
# =====================================================================

def peut_tenir(caisse, utilisateur):
    """
    Qui écrit dans une caisse : son détenteur, la direction, et les
    comptables de la filiale. Pas n'importe quel salarié.
    """
    if est_direction(utilisateur):
        return True
    if caisse.detenteur_id == utilisateur.pk:
        return True
    return (utilisateur.role == "COMPTABLE"
            and utilisateur.filiale_id == caisse.filiale_id)


def caisses_visibles(utilisateur):
    """Caisses consultables : celles de sa filiale, toutes pour la direction."""
    queryset = Caisse.objects.select_related("filiale", "detenteur")

    if est_direction(utilisateur):
        return queryset
    if not (utilisateur and utilisateur.is_authenticated):
        return queryset.none()

    filiale_id = getattr(utilisateur, "filiale_id", None)
    if filiale_id is None:
        return queryset.none()

    return queryset.filter(filiale_id=filiale_id)


# =====================================================================
# Mouvements
# =====================================================================

def alimenter(caisse, montant, acteur, justificatif=None, reference="",
              motif="", jour=None):
    """
    Fait entrer de l'argent en caisse.

    Exige une preuve — justificatif ou référence de transaction. C'est la
    règle qui distingue une caisse tenue d'un chiffre déclaré : on
    n'augmente pas un solde sur parole.
    """
    montant = Decimal(str(montant))

    if montant <= 0:
        raise OperationRefusee("Le montant d'une alimentation doit être positif.")

    if not (justificatif or reference.strip()):
        raise OperationRefusee(
            "Une alimentation exige une preuve : justificatif (chèque, reçu) "
            "ou référence de transaction.")

    if not peut_tenir(caisse, acteur):
        raise OperationRefusee("Vous ne tenez pas cette caisse.")

    mouvement = MouvementCaisse.objects.create(
        caisse=caisse,
        type_mouvement=MouvementCaisse.TypeMouvement.ALIMENTATION,
        montant=montant,
        justificatif=justificatif,
        reference=reference,
        motif=motif or "Alimentation de caisse",
        cree_par=acteur,
        date_operation=jour or timezone.localdate(),
    )

    enregistrer_action(
        acteur, "CAISSE_ALIMENTEE",
        f"{caisse.code} — {montant}", objet=caisse)

    return mouvement


def corriger(caisse, montant, acteur, motif, jour=None):
    """
    Écriture de correction, signée.

    Un écart de caisse se constate en ajoutant une ligne, jamais en
    retouchant l'historique : c'est ce qui permet de l'expliquer plus tard.
    """
    montant = Decimal(str(montant))

    if montant == 0:
        raise OperationRefusee("Une correction nulle n'a pas de sens.")
    if not motif.strip():
        raise OperationRefusee("Une correction doit être motivée.")
    if not peut_tenir(caisse, acteur):
        raise OperationRefusee("Vous ne tenez pas cette caisse.")

    mouvement = MouvementCaisse.objects.create(
        caisse=caisse,
        type_mouvement=MouvementCaisse.TypeMouvement.CORRECTION,
        montant=montant,
        motif=motif,
        cree_par=acteur,
        date_operation=jour or timezone.localdate(),
    )

    enregistrer_action(
        acteur, "CAISSE_CORRIGEE",
        f"{caisse.code} — {montant:+} : {motif}", objet=caisse)

    return mouvement


# =====================================================================
# Bons de sortie
# =====================================================================

def _reference(caisse):
    annee = timezone.now().year
    rang = BonSortie.objects.filter(
        caisse__filiale=caisse.filiale, date_creation__year=annee).count() + 1
    return f"{caisse.filiale.code}-BS-{annee}-{rang:04d}"


def deposer(caisse, demandeur, objet, montant, type_depense,
            moyen_transport="", destinataire=None, justificatif=None):
    """
    Dépose un bon de sortie.

    Le transport est autorisé d'office : une course ne s'arbitre pas avant
    d'être payée. Toute autre dépense est adressée à quelqu'un, dont le
    niveau doit correspondre au montant.
    """
    montant = Decimal(str(montant))

    if montant <= 0:
        raise OperationRefusee("Le montant doit être positif.")

    if not caisse.active:
        raise OperationRefusee("Cette caisse est fermée.")

    est_transport = type_depense == BonSortie.TypeDepense.TRANSPORT

    if est_transport:
        if not moyen_transport:
            raise OperationRefusee("Précisez le moyen de transport.")
        if (moyen_transport in BonSortie.MOYENS_AVEC_HISTORIQUE
                and not justificatif):
            raise OperationRefusee(
                f"Une course {moyen_transport.title()} exige son justificatif : "
                f"l'historique des transactions est disponible dans "
                f"l'application.")
        destinataire = None
    else:
        if moyen_transport:
            raise OperationRefusee(
                "Un moyen de transport ne se renseigne que sur une dépense "
                "de transport.")
        if destinataire is None:
            raise OperationRefusee(
                "Une sortie de caisse doit être adressée à la personne qui "
                "l'autorise.")
        if destinataire.pk == demandeur.pk:
            raise OperationRefusee(
                "Vous ne pouvez pas vous adresser le bon à vous-même.")
        if not destinataire_acceptable(destinataire, montant):
            niveaux = ", ".join(roles_autorises(montant))
            raise OperationRefusee(
                f"Au-delà de {seuil_direction()}, l'autorisation relève de : "
                f"{niveaux}.")

    bon = BonSortie(
        reference=_reference(caisse),
        caisse=caisse,
        demandeur=demandeur,
        destinataire=destinataire,
        objet=objet,
        montant=montant,
        type_depense=type_depense,
        moyen_transport=moyen_transport,
        justificatif=justificatif,
        statut=(BonSortie.Statut.AUTORISE if est_transport
                else BonSortie.Statut.EN_ATTENTE),
    )
    bon.save()

    enregistrer_action(
        demandeur, "BON_SORTIE_CREE",
        f"{bon.reference} — {objet} ({montant})", objet=bon)

    if not est_transport:
        validation.notifier_etape(
            bon, CIRCUIT_BON_SORTIE, 0, demandeur,
            "Bon de sortie à autoriser",
            f"{demandeur.nom_complet} — {objet} — {montant}")

    return bon


def decider(bon, acteur, autorise, motif=""):
    """Autorise ou refuse un bon de sortie adressé."""
    if bon.est_transport:
        raise OperationRefusee(
            "Une dépense de transport n'a pas à être autorisée.")

    with transaction.atomic():
        bon = (BonSortie.objects
               .select_for_update()
               .select_related("caisse", "demandeur", "destinataire")
               .get(pk=bon.pk))

        if bon.statut != BonSortie.Statut.EN_ATTENTE:
            raise OperationRefusee("Ce bon a déjà été traité.")

        try:
            decision, suivante = validation.enregistrer_decision(
                bon, CIRCUIT_BON_SORTIE, bon.etape_validation, acteur,
                bon.demandeur, autorise, motif)
        except ValidationRefusee as erreur:
            raise OperationRefusee(str(erreur)) from erreur

        bon.etape_validation = suivante
        bon.motif_decision = motif
        bon.statut = (BonSortie.Statut.AUTORISE if autorise
                      else BonSortie.Statut.REFUSE)
        bon.save()

        enregistrer_action(
            acteur, "BON_SORTIE_AUTORISE" if autorise else "BON_SORTIE_REFUSE",
            f"{bon.reference}"
            + (" (validation directe)" if decision.validation_directe else ""),
            objet=bon)

    envoyer_notification(
        bon.demandeur,
        "Bon de sortie autorisé" if autorise else "Bon de sortie refusé",
        f"{bon.reference} — {bon.objet}" + (f" — {motif}" if motif else ""),
        "SUCCESS" if autorise else "ERROR",
        objet=bon,
    )

    return bon


def payer(bon, acteur, jour=None):
    """
    Sort l'argent de la caisse.

    Le solde est vérifié sous verrou : sans cela, deux décaissements
    simultanés pourraient tous deux se croire couverts et vider la caisse
    au-delà de ce qu'elle contient.
    """
    with transaction.atomic():
        bon = (BonSortie.objects
               .select_for_update()
               .select_related("caisse", "demandeur")
               .get(pk=bon.pk))

        if bon.statut != BonSortie.Statut.AUTORISE:
            raise OperationRefusee(
                "Seul un bon autorisé peut être décaissé.")

        caisse = Caisse.objects.select_for_update().get(pk=bon.caisse_id)

        if not peut_tenir(caisse, acteur):
            raise OperationRefusee("Vous ne tenez pas cette caisse.")

        if caisse.solde < bon.montant:
            raise OperationRefusee(
                f"Solde insuffisant : {caisse.solde} disponible pour "
                f"{bon.montant} demandé.")

        MouvementCaisse.objects.create(
            caisse=caisse,
            type_mouvement=MouvementCaisse.TypeMouvement.SORTIE,
            montant=-bon.montant,
            motif=f"{bon.reference} — {bon.objet}",
            bon_sortie=bon,
            cree_par=acteur,
            date_operation=jour or timezone.localdate(),
        )

        bon.statut = BonSortie.Statut.PAYE
        bon.save(update_fields=["statut", "date_modification"])

        enregistrer_action(
            acteur, "BON_SORTIE_PAYE",
            f"{bon.reference} — {bon.montant}", objet=bon)

    envoyer_notification(
        bon.demandeur, "Bon de sortie payé",
        f"{bon.reference} — {bon.montant} remis.", "SUCCESS", objet=bon)

    return bon


def rendre_monnaie(bon, montant, acteur, motif="", jour=None):
    """
    Remet en caisse ce qui n'a pas été dépensé.

    Le cas courant : on avance 10 000, la course en coûte 7 000, les 3 000
    reviennent. Sans cette écriture, la caisse afficherait durablement
    moins qu'elle ne contient.
    """
    montant = Decimal(str(montant))

    if montant <= 0:
        raise OperationRefusee("Le montant rendu doit être positif.")

    if bon.statut != BonSortie.Statut.PAYE:
        raise OperationRefusee(
            "On ne rend de la monnaie que sur un bon déjà payé.")

    reste = bon.montant_paye - bon.montant_rendu
    if montant > reste:
        raise OperationRefusee(
            f"On ne peut pas rendre plus que ce qui est sorti : "
            f"{reste} restant.")

    if not (peut_tenir(bon.caisse, acteur) or acteur.pk == bon.demandeur_id):
        raise OperationRefusee("Vous ne pouvez pas agir sur ce bon.")

    mouvement = MouvementCaisse.objects.create(
        caisse=bon.caisse,
        type_mouvement=MouvementCaisse.TypeMouvement.RETOUR,
        montant=montant,
        motif=motif or f"Retour sur {bon.reference}",
        bon_sortie=bon,
        cree_par=acteur,
        date_operation=jour or timezone.localdate(),
    )

    enregistrer_action(
        acteur, "CAISSE_RETOUR",
        f"{bon.reference} — {montant} rendus", objet=bon)

    return mouvement
