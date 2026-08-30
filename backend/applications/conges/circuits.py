"""
Circuits de validation des congés.

Trois circuits, parce que trois situations différentes :

**Congé annuel — salarié.** Le responsable direct valide, puis la
direction confirme. La direction porte l'autorité : elle peut trancher
sans attendre le responsable (validation directe), ce qui est consigné.

**Congé annuel — direction (DG/PDG).** Un directeur n'a pas de supérieur
hiérarchique dans l'application. Sa demande part aux RH, puis à un autre
membre de la direction. Les deux étapes portent l'autorité : les RH comme
la direction peuvent conclure seuls.

**Permission exceptionnelle.** Une seule étape. L'article 45 de la
Convention Collective en fait un droit, non une faveur : le barème est
fixe, les jours ne se déduisent pas du solde, et faire approuver un décès
par le Directeur Général serait aussi lent qu'incongru. Exception faite
des permissions syndicales (10 j de congrès, 30 j de séminaire), longues
et discrétionnaires, qui suivent le circuit complet.

Dans tous les cas, RH et comptabilité sont **observateurs** : informés des
décisions, jamais sollicités pour trancher.
"""

from applications.validation.circuits import Circuit, Etape, Resolveur

from .convention import MotifPermission

#: Rôles tenus informés. Les RH suivent les absences et arbitrent ; la
#: comptabilité en a besoin pour la paie.
OBSERVATEURS = ("RH", "COMPTABLE")

#: Permissions assez longues et discrétionnaires pour mériter le circuit
#: complet, contrairement aux évènements familiaux qui sont de droit.
PERMISSIONS_DISCRETIONNAIRES = (
    MotifPermission.CONGRES_SYNDICAL,
    MotifPermission.SEMINAIRE_SYNDICAL_NATIONAL,
)


#: Salarié : responsable direct, puis direction.
CIRCUIT_SALARIE = Circuit(
    etapes=(
        Etape(
            cle="responsable",
            libelle="Validation du responsable hiérarchique",
            resolveur=Resolveur.HIERARCHIE,
            # Sans responsable renseigné, le chef de service prend le
            # relais ; à défaut, les RH — une demande ne doit jamais
            # rester sans destinataire.
            repli_role="RH",
        ),
        Etape(
            cle="direction",
            libelle="Confirmation de la direction",
            resolveur=Resolveur.DIRECTION,
            autorite=True,
        ),
    ),
    observateurs=OBSERVATEURS,
)


#: Direction : les RH, « et un autre PDG si nécessaire ».
#:
#: Une seule étape à deux titulaires, et non deux étapes successives : la
#: demande part aux RH, mais un autre membre de la direction peut tout
#: aussi bien trancher. Exiger les deux immobiliserait la demande dès que
#: l'un des deux est absent.
CIRCUIT_DIRECTION = Circuit(
    etapes=(
        Etape(
            cle="rh",
            libelle="Avis des RH ou d'un autre membre de la direction",
            resolveur=Resolveur.ROLE,
            parametre="RH",
            co_acteurs=((Resolveur.DIRECTION, ""),),
            autorite=True,
            repli_role="ADMINISTRATEUR",
        ),
    ),
    observateurs=OBSERVATEURS,
)


#: Permission de droit : une seule étape.
CIRCUIT_PERMISSION = Circuit(
    etapes=(
        Etape(
            cle="responsable",
            libelle="Validation du responsable hiérarchique",
            resolveur=Resolveur.HIERARCHIE,
            repli_role="RH",
        ),
    ),
    observateurs=OBSERVATEURS,
)


#: Rôles considérés comme « direction » pour le choix du circuit.
ROLES_DIRECTION = ("DIRECTEUR", "ADMINISTRATEUR")


def circuit_pour(demande):
    """
    Circuit applicable à une demande.

    Le PDG suit le même chemin que le DG : l'application ne distingue pas
    les deux, tous deux relèvent du rôle DIRECTEUR.
    """
    from .models import TypeConge

    if demande.type_conge == TypeConge.PERMISSION:
        if demande.motif_permission in PERMISSIONS_DISCRETIONNAIRES:
            return CIRCUIT_SALARIE
        return CIRCUIT_PERMISSION

    if demande.utilisateur.role in ROLES_DIRECTION:
        return CIRCUIT_DIRECTION

    return CIRCUIT_SALARIE
