"""
Soldes de congés : acquisition, disponibilité, consommation, expiration.

Le solde n'est jamais un compteur : c'est la somme des `MouvementConge` de
l'année. Toute correction s'écrit en ajoutant une écriture inverse, jamais
en retouchant l'historique — c'est ce qui permet de justifier un solde
ligne à ligne devant un salarié.

Règles RH appliquées (2026-08-21) : 2,5 jours par mois de service révolu à
compter de la date d'embauche, solde perdu au 31 décembre, pas de
demi-journée.
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum

from .models import DemandeConge, MouvementConge, TypeConge

User = get_user_model()

#: Jours acquis par mois de service révolu.
ACQUISITION_MENSUELLE = Decimal("2.5")

#: Plafond annuel : 12 mois × 2,5 jours.
PLAFOND_ANNUEL = Decimal("30")


# =====================================================================
# Lecture des soldes
# =====================================================================

def solde(utilisateur, annee=None):
    """Solde acquis et non consommé pour l'année (somme du registre)."""
    annee = annee or date.today().year

    total = MouvementConge.objects.filter(
        utilisateur=utilisateur, annee=annee,
    ).aggregate(total=Sum("jours"))["total"]

    return total or Decimal("0")


def jours_reserves(utilisateur, annee=None):
    """
    Jours mobilisés par des demandes en attente de validation.

    Sans cette réserve, deux demandes soumises coup sur coup pourraient
    être validées séparément et faire passer le solde sous zéro : chacune
    aurait vu un solde encore intact.
    """
    annee = annee or date.today().year

    total = DemandeConge.objects.filter(
        utilisateur=utilisateur,
        statut=DemandeConge.Statut.EN_ATTENTE,
        type_conge=TypeConge.ANNUEL,
        date_debut__year=annee,
    ).aggregate(total=Sum("jours_ouvres"))["total"]

    return Decimal(total or 0)


def solde_disponible(utilisateur, annee=None):
    """Ce qu'il reste réellement à poser : acquis moins jours réservés."""
    return solde(utilisateur, annee) - jours_reserves(utilisateur, annee)


def situation(utilisateur, annee=None):
    """Vue d'ensemble du compteur d'un salarié, pour l'API et l'affichage."""
    annee = annee or date.today().year

    mouvements = MouvementConge.objects.filter(utilisateur=utilisateur, annee=annee)

    def _somme(type_mouvement):
        total = mouvements.filter(type_mouvement=type_mouvement).aggregate(
            total=Sum("jours"))["total"]
        return total or Decimal("0")

    return {
        "annee": annee,
        "acquis": _somme(MouvementConge.TypeMouvement.ACQUISITION),
        "pris": abs(_somme(MouvementConge.TypeMouvement.CONSOMMATION)),
        "reserves": jours_reserves(utilisateur, annee),
        "solde": solde(utilisateur, annee),
        "disponible": solde_disponible(utilisateur, annee),
    }


# =====================================================================
# Acquisition mensuelle
# =====================================================================

def _anniversaire_mensuel(embauche, annee, mois):
    """
    Jour du mois où tombe l'anniversaire mensuel d'embauche.

    Une embauche le 31 janvier n'a pas de 31 février : l'anniversaire est
    ramené au dernier jour du mois, sinon ces salariés n'acquerraient
    jamais leurs jours certains mois.
    """
    dernier_jour = monthrange(annee, mois)[1]
    return date(annee, mois, min(embauche.day, dernier_jour))


def echeances_acquisition(embauche, jusqu_a):
    """
    Dates d'acquisition échues entre l'embauche et `jusqu_a` inclus.

    Une échéance tombe à chaque anniversaire mensuel de la date
    d'embauche : entré le 15 septembre, le salarié acquiert ses premiers
    2,5 jours le 15 octobre — un mois de service **révolu**, jamais
    d'avance.
    """
    if embauche is None or jusqu_a < embauche:
        return []

    echeances = []
    annee, mois = embauche.year, embauche.month

    while True:
        mois += 1
        if mois > 12:
            annee, mois = annee + 1, 1

        echeance = _anniversaire_mensuel(embauche, annee, mois)
        if echeance > jusqu_a:
            break
        echeances.append(echeance)

    return echeances


def crediter_acquisitions(utilisateur, jusqu_a=None):
    """
    Crédite les acquisitions échues et non encore enregistrées.

    Idempotente : chaque échéance déjà présente au registre est ignorée, et
    une contrainte d'unicité en base rattrape les cas de concurrence. La
    tâche mensuelle étant rejouable (ACKS_LATE), un double crédit
    donnerait des jours qui n'existent pas.

    Renvoie le nombre d'acquisitions créées.
    """
    jusqu_a = jusqu_a or date.today()

    if utilisateur.date_embauche is None:
        return 0

    echeances = echeances_acquisition(utilisateur.date_embauche, jusqu_a)
    if not echeances:
        return 0

    deja_creditees = set(
        MouvementConge.objects.filter(
            utilisateur=utilisateur,
            type_mouvement=MouvementConge.TypeMouvement.ACQUISITION,
            date_effet__in=echeances,
        ).values_list("date_effet", flat=True)
    )

    a_crediter = [e for e in echeances if e not in deja_creditees]
    if not a_crediter:
        return 0

    MouvementConge.objects.bulk_create(
        [
            MouvementConge(
                utilisateur=utilisateur,
                annee=echeance.year,
                type_mouvement=MouvementConge.TypeMouvement.ACQUISITION,
                jours=ACQUISITION_MENSUELLE,
                date_effet=echeance,
                motif="Acquisition mensuelle",
            )
            for echeance in a_crediter
        ],
        # Filet de sécurité si deux exécutions se croisent : la contrainte
        # d'unicité tranche, sans faire échouer toute la tâche.
        ignore_conflicts=True,
    )

    return len(a_crediter)


def crediter_toutes_les_acquisitions(jusqu_a=None):
    """Acquisition mensuelle pour l'ensemble des salariés actifs."""
    total = 0
    for utilisateur in User.objects.filter(
        is_active=True, date_embauche__isnull=False,
    ):
        total += crediter_acquisitions(utilisateur, jusqu_a)
    return total


# =====================================================================
# Expiration de fin d'année
# =====================================================================

def expirer_solde(utilisateur, annee):
    """
    Solde perdu au 31 décembre, conformément à la règle RH.

    L'écriture d'expiration matérialise la perte au registre plutôt que de
    remettre un compteur à zéro : le salarié peut voir combien de jours il
    a perdus, et quand.
    """
    restant = solde(utilisateur, annee)
    if restant <= 0:
        return Decimal("0")

    MouvementConge.objects.create(
        utilisateur=utilisateur,
        annee=annee,
        type_mouvement=MouvementConge.TypeMouvement.EXPIRATION,
        jours=-restant,
        date_effet=date(annee, 12, 31),
        motif=f"Solde non pris au 31/12/{annee} — perdu",
    )

    return restant


def expirer_tous_les_soldes(annee=None):
    """
    Clôture l'année : purge les soldes non pris de tous les salariés.

    Idempotente : une fois le solde ramené à zéro, une seconde exécution
    n'écrit plus rien.
    """
    annee = annee or date.today().year

    total = Decimal("0")
    for utilisateur in User.objects.filter(is_active=True):
        total += expirer_solde(utilisateur, annee)

    return total


# =====================================================================
# Consommation liée aux demandes
# =====================================================================

def consommer(demande):
    """
    Débite le solde à la validation d'une demande.

    Sans effet pour les types qui ne se décomptent pas (maladie,
    maternité…) et si la demande a déjà été débitée.
    """
    if not demande.decompte_le_solde or demande.jours_ouvres == 0:
        return None

    with transaction.atomic():
        deja = MouvementConge.objects.filter(
            demande=demande,
            type_mouvement=MouvementConge.TypeMouvement.CONSOMMATION,
        ).exists()
        if deja:
            return None

        return MouvementConge.objects.create(
            utilisateur=demande.utilisateur,
            annee=demande.date_debut.year,
            type_mouvement=MouvementConge.TypeMouvement.CONSOMMATION,
            jours=Decimal(-demande.jours_ouvres),
            date_effet=demande.date_debut,
            demande=demande,
            motif=f"Congé du {demande.date_debut:%d/%m/%Y} "
                  f"au {demande.date_fin:%d/%m/%Y}",
        )


def restituer(demande):
    """
    Recrédite le solde quand un congé déjà validé est annulé.

    Ne rend que ce qui a effectivement été débité : une demande annulée
    avant validation n'a rien consommé, il n'y a rien à rendre.
    """
    with transaction.atomic():
        consomme = MouvementConge.objects.filter(
            demande=demande,
            type_mouvement=MouvementConge.TypeMouvement.CONSOMMATION,
        ).aggregate(total=Sum("jours"))["total"]

        if not consomme:
            return None

        deja_rendu = MouvementConge.objects.filter(
            demande=demande,
            type_mouvement=MouvementConge.TypeMouvement.RESTITUTION,
        ).exists()
        if deja_rendu:
            return None

        return MouvementConge.objects.create(
            utilisateur=demande.utilisateur,
            annee=demande.date_debut.year,
            type_mouvement=MouvementConge.TypeMouvement.RESTITUTION,
            jours=abs(consomme),
            date_effet=date.today(),
            demande=demande,
            motif="Annulation du congé",
        )
