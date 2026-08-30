"""
Circuits de validation : qui doit approuver quoi, dans quel ordre.

Ce module ne connaît ni les congés ni les bons de sortie. Il décrit un
circuit — une suite d'étapes, chacune sachant désigner ses acteurs — et
laisse chaque module composer le sien.

Pourquoi un socle commun plutôt qu'un circuit par module : l'application
en comptait déjà deux, écrits séparément (visas documentaires par rôle,
validation des congés par la hiérarchie), et les besoins qui arrivent en
ajoutent d'autres. Chaque copie réimplémente les mêmes règles — qui peut
agir, comment consigner la décision, comment prévenir le suivant — et
chacune peut se tromper indépendamment. Le verrouillage de ligne, par
exemple, n'existait que dans l'une des deux.

**Résolveurs d'acteurs.** C'est la différence de fond entre les circuits
existants, et le socle doit les porter tous les deux :

- `HIERARCHIE`   : le responsable du demandeur — *mon* chef, pas n'importe
                   quel chef. C'est la règle des congés.
- `CHEF_SERVICE` : le chef du service du demandeur.
- `ROLE`         : tout titulaire d'un rôle dans la filiale du demandeur —
                   la règle des visas documentaires.
- `PERSONNE`     : une personne nommément désignée sur la demande, par
                   exemple le destinataire d'un bon de sortie.
- `DIRECTION`    : administrateur ou directeur, quel que soit le service.

**Validation directe.** Une étape peut être marquée `autorite=True` : ses
acteurs peuvent trancher sans attendre les étapes qui les précèdent. Ce
n'est pas un contournement caché — la décision consigne explicitement les
étapes sautées, et qui les a sautées.
"""

from dataclasses import dataclass, field
from enum import Enum


class Resolveur(str, Enum):
    """Manière de désigner les acteurs habilités à trancher une étape."""

    HIERARCHIE = "HIERARCHIE"
    CHEF_SERVICE = "CHEF_SERVICE"
    ROLE = "ROLE"
    PERSONNE = "PERSONNE"
    DIRECTION = "DIRECTION"


@dataclass(frozen=True)
class Etape:
    """
    Une étape de validation.

    - `cle`        : identifiant stable, consigné dans l'historique ;
    - `libelle`    : ce que lit l'utilisateur ;
    - `resolveur`  : comment désigner les acteurs ;
    - `parametre`  : rôle attendu (ROLE) ou nom de l'attribut portant la
                     personne désignée (PERSONNE) ;
    - `co_acteurs` : autres désignations valables pour la même étape ;
    - `autorite`   : ses acteurs peuvent valider directement, sans attendre
                     les étapes précédentes ;
    - `repli_role` : rôle qui prend le relais quand le résolveur ne désigne
                     personne — un salarié sans responsable ne doit pas
                     rester bloqué.
    """

    cle: str
    libelle: str
    resolveur: Resolveur
    parametre: str = ""
    autorite: bool = False
    repli_role: str = ""
    #: Modes de désignation supplémentaires, réunis au principal — couples
    #: (résolveur, paramètre). Sert quand plusieurs personnes de nature
    #: différente peuvent trancher indifféremment la MÊME étape : la
    #: demande d'un directeur part aux RH « et à un autre PDG si
    #: nécessaire », ce qui est une seule étape à deux titulaires, non deux
    #: étapes successives.
    co_acteurs: tuple = ()


@dataclass(frozen=True)
class Circuit:
    """Suite ordonnée d'étapes, plus les rôles tenus informés."""

    etapes: tuple
    #: Rôles prévenus des décisions sans avoir à trancher (RH, comptabilité).
    observateurs: tuple = field(default_factory=tuple)

    def __post_init__(self):
        cles = [e.cle for e in self.etapes]
        if len(cles) != len(set(cles)):
            raise ValueError(
                f"Clés d'étape en double dans le circuit : {cles}")

    def etape(self, index):
        """Étape à l'index donné, ou None si le circuit est terminé."""
        if 0 <= index < len(self.etapes):
            return self.etapes[index]
        return None

    def index_de(self, cle):
        for index, etape in enumerate(self.etapes):
            if etape.cle == cle:
                return index
        return None

    def __len__(self):
        return len(self.etapes)


def resoudre_acteurs(etape, demandeur, objet=None):
    """
    Utilisateurs habilités à trancher cette étape pour ce demandeur.

    Renvoie un ensemble d'identifiants, réunissant le résolveur principal
    et les éventuels co-acteurs. Le demandeur en est toujours exclu :
    personne ne valide sa propre demande, quel que soit son rôle.
    """
    identifiants = _designer(etape.resolveur, etape.parametre, demandeur, objet)

    for resolveur, parametre in etape.co_acteurs:
        identifiants |= _designer(resolveur, parametre, demandeur, objet)

    # Repli : sans acteur désigné, l'étape resterait sans titulaire et la
    # demande dormirait indéfiniment.
    if not identifiants and etape.repli_role:
        identifiants |= _designer(Resolveur.ROLE, etape.repli_role,
                                  demandeur, objet, toutes_filiales=True)

    identifiants.discard(getattr(demandeur, "pk", None))
    return identifiants


def _designer(resolveur, parametre, demandeur, objet=None,
              toutes_filiales=False):
    """Applique un seul mode de désignation."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    identifiants = set()

    if resolveur == Resolveur.HIERARCHIE:
        responsable = getattr(demandeur, "responsable_hierarchique", None)
        if responsable is not None and responsable.is_active:
            identifiants.add(responsable.pk)

    elif resolveur == Resolveur.CHEF_SERVICE:
        service = getattr(demandeur, "service", None)
        if service is not None and service.chef_id:
            identifiants.add(service.chef_id)

    elif resolveur == Resolveur.ROLE:
        identifiants.update(
            User.objects
            .filter(is_active=True, role=parametre,
                    **({} if toutes_filiales else
                       {"filiale_id": getattr(demandeur, "filiale_id", None)}))
            .values_list("pk", flat=True)
        )

    elif resolveur == Resolveur.PERSONNE:
        designe = getattr(objet, parametre, None) if objet else None
        identifiant = getattr(designe, "pk", designe)
        if identifiant:
            identifiants.add(identifiant)

    elif resolveur == Resolveur.DIRECTION:
        identifiants.update(
            User.objects
            .filter(is_active=True, role__in=("ADMINISTRATEUR", "DIRECTEUR"))
            .values_list("pk", flat=True)
        )

    return identifiants


def peut_agir(circuit, index, utilisateur, demandeur, objet=None):
    """
    True si `utilisateur` peut trancher l'étape courante — soit parce qu'il
    en est un acteur, soit parce qu'il tient une étape d'autorité ultérieure
    et exerce sa validation directe.
    """
    if utilisateur is None or not utilisateur.is_authenticated:
        return False
    if getattr(demandeur, "pk", None) == utilisateur.pk:
        return False

    etape = circuit.etape(index)
    if etape is None:
        return False

    if utilisateur.pk in resoudre_acteurs(etape, demandeur, objet):
        return True

    return bool(etapes_sautees(circuit, index, utilisateur, demandeur, objet))


def etapes_sautees(circuit, index, utilisateur, demandeur, objet=None):
    """
    Étapes que `utilisateur` court-circuiterait en validant maintenant.

    Vide s'il est acteur de l'étape courante (rien n'est sauté) ou s'il ne
    détient aucune autorité en aval. La liste renvoyée est consignée dans
    la décision : une validation directe doit rester lisible après coup.
    """
    etape_courante = circuit.etape(index)
    if etape_courante is None:
        return []

    if utilisateur.pk in resoudre_acteurs(etape_courante, demandeur, objet):
        return []

    for suivant in range(index, len(circuit)):
        etape = circuit.etape(suivant)
        if not etape.autorite:
            continue
        if utilisateur.pk in resoudre_acteurs(etape, demandeur, objet):
            return [circuit.etape(i).cle for i in range(index, suivant)]

    return []
