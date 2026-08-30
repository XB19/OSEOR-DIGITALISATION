"""
Autorisation d'un bon de sortie.

Le bon est **adressé à quelqu'un** : c'est le résolveur `PERSONNE` du socle
de validation, ajouté précisément pour ce cas. La direction porte
l'autorité et peut trancher directement.

**Le destinataire ne se choisit pas librement.** Laisser le demandeur
désigner qui il veut invite à router vers la personne la plus
accommodante — une faiblesse de contrôle réelle dès qu'il s'agit
d'espèces. Le niveau requis se déduit donc du montant ; le demandeur peut
nommer une personne, à condition qu'elle soit au moins à ce niveau.
"""

from decimal import Decimal

from django.conf import settings

from applications.validation.circuits import Circuit, Etape, Resolveur

#: Au-delà de ce montant, seule la direction autorise. En deçà, un chef de
#: service suffit. Réglable sans redéploiement.
SEUIL_DIRECTION_DEFAUT = Decimal("100000")

#: Rôles admis comme destinataires selon le niveau requis.
NIVEAU_SERVICE = ("CHEF_SERVICE", "COMPTABLE", "SECRETAIRE",
                  "DIRECTEUR", "ADMINISTRATEUR")
NIVEAU_DIRECTION = ("DIRECTEUR", "ADMINISTRATEUR")


#: Une étape, adressée à la personne nommée sur le bon.
CIRCUIT_BON_SORTIE = Circuit(
    etapes=(
        Etape(
            cle="destinataire",
            libelle="Autorisation du destinataire",
            resolveur=Resolveur.PERSONNE,
            parametre="destinataire",
            co_acteurs=((Resolveur.DIRECTION, ""),),
            autorite=True,
            repli_role="DIRECTEUR",
        ),
    ),
    observateurs=("COMPTABLE",),
)


def seuil_direction():
    return Decimal(str(getattr(
        settings, "CAISSE_SEUIL_DIRECTION", SEUIL_DIRECTION_DEFAUT)))


def roles_autorises(montant):
    """Rôles admis comme destinataires pour ce montant."""
    return (NIVEAU_DIRECTION if Decimal(montant) > seuil_direction()
            else NIVEAU_SERVICE)


def destinataire_acceptable(destinataire, montant):
    """
    True si cette personne peut autoriser une dépense de ce montant.

    Le demandeur garde la main sur *qui* précisément, jamais sur le niveau
    exigé : au-delà du seuil, un chef de service ne suffit plus.
    """
    if destinataire is None:
        return False
    return destinataire.role in roles_autorises(montant)
