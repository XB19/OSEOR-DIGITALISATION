"""
Conduite d'une procédure disciplinaire.

Toutes les garanties de l'article 58 sont appliquées ici, et refusent
plutôt qu'elles n'avertissent : le salarié s'explique avant toute
sanction, la sanction respecte le barème, elle intervient dans les deux
mois de la preuve, et une même faute n'est sanctionnée qu'une fois.
"""

from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from applications.journalisation.services import enregistrer_action
from applications.notifications.services import envoyer_notification
from config.permissions import RH, est_direction

from .convention import DELAI_SANCTION_MOIS, duree_valide, regle
from .models import ExplicationSalarie, ProcedureDisciplinaire, Sanction


class ProcedureRefusee(Exception):
    """Garantie de l'article 58 non respectée ; message destiné à l'appelant."""


# =====================================================================
# Habilitations et périmètre
# =====================================================================

def peut_instruire(utilisateur):
    """Qui ouvre et instruit un dossier : les RH et la direction."""
    return est_direction(utilisateur) or utilisateur.role == RH


def peut_prononcer(utilisateur):
    """
    Qui prononce une sanction.

    L'article 58 la réserve au **directeur de l'établissement**. Les RH
    instruisent, la direction tranche : c'est une séparation voulue par le
    texte, pas une commodité.
    """
    return est_direction(utilisateur)


def procedures_visibles(utilisateur):
    """
    Périmètre de lecture, le plus étroit de l'application.

    Le salarié voit son propre dossier ; les RH et la direction voient
    ceux de leur périmètre. Personne d'autre — ni le chef de service, ni
    les collègues.
    """
    queryset = ProcedureDisciplinaire.objects.select_related(
        "salarie", "filiale", "ouverte_par")

    if not (utilisateur and utilisateur.is_authenticated):
        return queryset.none()

    if est_direction(utilisateur):
        return queryset

    if utilisateur.role == RH:
        filiale_id = getattr(utilisateur, "filiale_id", None)
        if filiale_id is None:
            return queryset.none()
        return queryset.filter(filiale_id=filiale_id)

    return queryset.filter(salarie=utilisateur)


def _reference(filiale):
    annee = timezone.now().year
    rang = ProcedureDisciplinaire.objects.filter(
        filiale=filiale, date_ouverture__year=annee).count() + 1
    return f"{filiale.code}-DISC-{annee}-{rang:04d}"


# =====================================================================
# Conduite du dossier
# =====================================================================

def ouvrir(salarie, faits, date_faits, date_preuve, acteur,
           qualification=ProcedureDisciplinaire.Qualification.FAUTE_SIMPLE,
           faute_lourde_invoquee="", mise_a_pied_conservatoire=False):
    """Ouvre un dossier disciplinaire."""
    if not peut_instruire(acteur):
        raise ProcedureRefusee(
            "Seuls les RH et la direction ouvrent une procédure disciplinaire.")

    if salarie.pk == acteur.pk:
        raise ProcedureRefusee(
            "Vous ne pouvez pas ouvrir une procédure contre vous-même.")

    if not faits.strip():
        raise ProcedureRefusee("Les faits reprochés doivent être décrits.")

    if date_preuve < date_faits:
        raise ProcedureRefusee("La preuve ne peut pas précéder les faits.")

    if salarie.filiale is None:
        raise ProcedureRefusee(
            "Le salarié n'est rattaché à aucune filiale.")

    procedure = ProcedureDisciplinaire.objects.create(
        reference=_reference(salarie.filiale),
        salarie=salarie,
        filiale=salarie.filiale,
        faits=faits,
        date_faits=date_faits,
        date_preuve=date_preuve,
        qualification=qualification,
        faute_lourde_invoquee=faute_lourde_invoquee,
        mise_a_pied_conservatoire=mise_a_pied_conservatoire,
        date_mise_a_pied=(timezone.localdate()
                          if mise_a_pied_conservatoire else None),
        ouverte_par=acteur,
    )

    enregistrer_action(
        acteur, "DISCIPLINE_OUVERTE",
        f"{procedure.reference} — {salarie.nom_complet}", objet=procedure)

    # Le salarié est informé : il ne peut s'expliquer sur des faits qu'il
    # ignore.
    envoyer_notification(
        salarie,
        "Procédure disciplinaire ouverte",
        f"{procedure.reference} — vous serez invité à fournir vos "
        f"explications, éventuellement assisté d'un délégué du personnel.",
        "WARNING",
        objet=procedure,
    )

    return procedure


def demander_explications(procedure, acteur):
    """Invite formellement le salarié à s'expliquer."""
    if not peut_instruire(acteur):
        raise ProcedureRefusee("Vous n'instruisez pas ce dossier.")

    if procedure.est_close:
        raise ProcedureRefusee("Cette procédure est close.")

    procedure.statut = ProcedureDisciplinaire.Statut.EXPLICATIONS_DEMANDEES
    procedure.save(update_fields=["statut", "date_modification"])

    envoyer_notification(
        procedure.salarie,
        "Explications demandées",
        f"{procedure.reference} — vous êtes invité à fournir vos explications, "
        f"écrites ou verbales. Vous pouvez vous faire assister d'un délégué "
        f"du personnel.",
        "WARNING",
        objet=procedure,
    )

    enregistrer_action(
        acteur, "DISCIPLINE_EXPLICATIONS_DEMANDEES",
        procedure.reference, objet=procedure)

    return procedure


def consigner_explications(procedure, acteur, mode, contenu="",
                           delegue_present=False, piece_jointe=None):
    """
    Consigne les explications du salarié.

    Le refus de s'expliquer se consigne aussi : la garantie est d'avoir été
    entendu, pas d'avoir parlé. Sans cette trace, une procédure resterait
    bloquée dès qu'un salarié garde le silence.
    """
    if procedure.est_close:
        raise ProcedureRefusee("Cette procédure est close.")

    autorise = peut_instruire(acteur) or acteur.pk == procedure.salarie_id
    if not autorise:
        raise ProcedureRefusee(
            "Seuls le salarié concerné, les RH et la direction peuvent "
            "consigner des explications.")

    if mode != ExplicationSalarie.Mode.REFUS and not contenu.strip():
        raise ProcedureRefusee("La teneur des explications doit être consignée.")

    explication = ExplicationSalarie.objects.create(
        procedure=procedure,
        mode=mode,
        contenu=contenu,
        delegue_present=delegue_present,
        piece_jointe=piece_jointe,
        consignee_par=acteur,
    )

    procedure.statut = ProcedureDisciplinaire.Statut.EXPLICATIONS_FOURNIES
    procedure.save(update_fields=["statut", "date_modification"])

    enregistrer_action(
        acteur, "DISCIPLINE_EXPLICATIONS",
        f"{procedure.reference} — {explication.get_mode_display()}",
        objet=procedure)

    return explication


def prononcer(procedure, acteur, type_sanction, motif, duree_jours=None,
              jour=None):
    """
    Prononce la sanction, après avoir vérifié les quatre garanties de
    l'article 58.

    Chacune refuse plutôt qu'elle n'avertit : une sanction irrégulière est
    contestable, et le logiciel n'a pas à laisser produire une décision que
    l'Inspection du Travail annulerait.
    """
    jour = jour or timezone.localdate()

    if not peut_prononcer(acteur):
        raise ProcedureRefusee(
            "L'article 58 réserve le prononcé au directeur de "
            "l'établissement.")

    # Non bis in idem : le dire explicitement plutôt que « procédure close »,
    # qui masquerait la règle réellement opposée au demandeur.
    if procedure.statut == ProcedureDisciplinaire.Statut.SANCTIONNEE:
        raise ProcedureRefusee(
            "Une sanction a déjà été prononcée : la même faute ne peut faire "
            "l'objet de deux sanctions (article 58).")

    if procedure.est_close:
        raise ProcedureRefusee(
            "Cette procédure est classée : aucune sanction ne peut plus être "
            "prononcée.")

    # 1. Le salarié s'explique d'abord.
    if not procedure.explications_recueillies:
        raise ProcedureRefusee(
            "Le salarié doit avoir fourni ses explications — ou son refus "
            "doit avoir été consigné — avant toute sanction.")

    # 2. Deux mois à compter de l'établissement de la preuve.
    if jour > procedure.date_limite_sanction:
        raise ProcedureRefusee(
            f"Le délai de {DELAI_SANCTION_MOIS} mois de l'article 58 est "
            f"dépassé : la preuve date du {procedure.date_preuve:%d/%m/%Y}, "
            f"la sanction n'était possible que jusqu'au "
            f"{procedure.date_limite_sanction:%d/%m/%Y}.")

    # 3. Barème et durée.
    r = regle(type_sanction)
    if r is None:
        raise ProcedureRefusee("Sanction inconnue au barème de l'article 58.")

    erreur = duree_valide(type_sanction, duree_jours)
    if erreur:
        raise ProcedureRefusee(erreur)

    if (r["faute_lourde_requise"]
            and procedure.qualification
            != ProcedureDisciplinaire.Qualification.FAUTE_LOURDE):
        raise ProcedureRefusee(
            "Le licenciement sans préavis suppose une faute lourde "
            "(article 58 e).")

    if not motif.strip():
        raise ProcedureRefusee("La sanction doit être motivée par écrit.")

    # 4. Non bis in idem — garanti par la relation un-à-un, rattrapé ici
    #    pour rendre un message lisible plutôt qu'une erreur d'intégrité.
    try:
        with transaction.atomic():
            sanction = Sanction.objects.create(
                procedure=procedure,
                type_sanction=type_sanction,
                duree_jours=duree_jours,
                motif=motif,
                prononcee_par=acteur,
                date_prononce=jour,
            )

            procedure.statut = ProcedureDisciplinaire.Statut.SANCTIONNEE
            procedure.save(update_fields=["statut", "date_modification"])
    except IntegrityError as erreur_integrite:
        raise ProcedureRefusee(
            "Une sanction a déjà été prononcée : la même faute ne peut faire "
            "l'objet de deux sanctions.") from erreur_integrite

    enregistrer_action(
        acteur, "DISCIPLINE_SANCTION",
        f"{procedure.reference} — {sanction.libelle_bareme}", objet=procedure)

    envoyer_notification(
        procedure.salarie,
        "Sanction disciplinaire",
        f"{procedure.reference} — {sanction.libelle_bareme}. "
        f"La décision vous sera signifiée par écrit.",
        "ERROR",
        objet=procedure,
    )

    return sanction


def enregistrer_formalites(sanction, acteur, date_notification=None,
                           date_inspection_travail=None):
    """
    Consigne la signification au salarié et l'ampliation à l'Inspection du
    Travail, toutes deux imposées par l'article 58.

    Suivies plutôt qu'imposées au prononcé : elles interviennent après, et
    le dossier doit pouvoir montrer qu'elles restent à faire.
    """
    if not peut_instruire(acteur):
        raise ProcedureRefusee("Vous n'instruisez pas ce dossier.")

    champs = []
    if date_notification:
        sanction.date_notification = date_notification
        champs.append("date_notification")
    if date_inspection_travail:
        sanction.date_inspection_travail = date_inspection_travail
        champs.append("date_inspection_travail")

    if not champs:
        raise ProcedureRefusee("Aucune formalité à enregistrer.")

    sanction.save(update_fields=champs)

    enregistrer_action(
        acteur, "DISCIPLINE_FORMALITES",
        f"{sanction.procedure.reference} — {', '.join(champs)}",
        objet=sanction.procedure)

    return sanction


def classer(procedure, acteur, motif):
    """
    Classe le dossier sans suite.

    Le dossier reste : c'est précisément ce qui permet de démontrer, plus
    tard, qu'il a été classé — et pourquoi.
    """
    if not peut_instruire(acteur):
        raise ProcedureRefusee("Vous n'instruisez pas ce dossier.")

    if procedure.est_close:
        raise ProcedureRefusee("Cette procédure est déjà close.")

    if not motif.strip():
        raise ProcedureRefusee("Un classement doit être motivé.")

    procedure.statut = ProcedureDisciplinaire.Statut.CLASSEE
    procedure.motif_classement = motif
    procedure.mise_a_pied_conservatoire = False
    procedure.save(update_fields=[
        "statut", "motif_classement", "mise_a_pied_conservatoire",
        "date_modification"])

    enregistrer_action(
        acteur, "DISCIPLINE_CLASSEE",
        f"{procedure.reference} — {motif}", objet=procedure)

    envoyer_notification(
        procedure.salarie,
        "Procédure classée sans suite",
        f"{procedure.reference} — {motif}",
        "SUCCESS",
        objet=procedure,
    )

    return procedure


def procedures_a_echeance(dans_jours=15, jour=None):
    """
    Dossiers dont le délai de deux mois approche sans sanction ni
    classement.

    Passé ce délai plus rien n'est possible : un dossier oublié devient une
    faute impunie, et le salarié reste sous le coup d'une procédure ouverte
    indéfiniment. Les deux méritent un rappel.
    """
    from datetime import timedelta

    jour = jour or date.today()
    limite = jour + timedelta(days=dans_jours)

    return ProcedureDisciplinaire.objects.filter(
        statut__in=(
            ProcedureDisciplinaire.Statut.OUVERTE,
            ProcedureDisciplinaire.Statut.EXPLICATIONS_DEMANDEES,
            ProcedureDisciplinaire.Statut.EXPLICATIONS_FOURNIES,
        ),
    ).select_related("salarie", "filiale", "ouverte_par")


def alerter_delais(dans_jours=15, jour=None):
    """Prévient les instructeurs des dossiers dont le délai expire bientôt."""
    from datetime import timedelta

    jour = jour or date.today()
    limite = jour + timedelta(days=dans_jours)

    envoyees = 0
    for procedure in procedures_a_echeance(dans_jours, jour):
        if not (jour <= procedure.date_limite_sanction <= limite):
            continue

        restant = (procedure.date_limite_sanction - jour).days
        envoyer_notification(
            procedure.ouverte_par,
            "Délai disciplinaire bientôt expiré",
            f"{procedure.reference} — {procedure.salarie.nom_complet} : "
            f"plus que {restant} jour(s) pour prononcer une sanction "
            f"(article 58).",
            "WARNING",
            objet=procedure,
        )
        envoyees += 1

    return envoyees
