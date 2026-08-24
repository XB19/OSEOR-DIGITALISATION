"""
Vocabulaire des rôles et permissions DRF de la plateforme OSEOR.

Point d'entrée unique pour deux questions qui se posent dans chaque module :

- « qui a le droit d'appeler cette vue ? »      -> classes de permission
- « quelles lignes cet utilisateur voit-il ? »  -> `restreindre_a_la_filiale`

Jusqu'ici la réponse était réécrite à la main dans chaque viewset
(`u.role in ("ADMINISTRATEUR", "DIRECTEUR")`), ce qui multipliait les
occasions d'oublier un rôle ou une filiale. Les nouveaux modules
s'appuient sur ce module ; les anciens y sont ramenés au fur et à mesure.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


# =====================================================================
# Rôles
# =====================================================================

ADMINISTRATEUR = "ADMINISTRATEUR"
DIRECTEUR = "DIRECTEUR"
SECRETAIRE = "SECRETAIRE"
CHEF_SERVICE = "CHEF_SERVICE"
COMPTABLE = "COMPTABLE"
RH = "RH"
EMPLOYE = "EMPLOYE"

#: Voient l'ensemble du groupe et peuvent viser n'importe quelle étape.
DIRECTION = (ADMINISTRATEUR, DIRECTEUR)

#: Gèrent les réservations de salles et les audiences de leur filiale.
GESTION_BUREAU = (SECRETAIRE, ADMINISTRATEUR)


def est_direction(utilisateur) -> bool:
    """Administrateur ou Directeur Général : accès transverse au groupe."""
    return bool(
        utilisateur
        and utilisateur.is_authenticated
        and utilisateur.role in DIRECTION
    )


# =====================================================================
# Classes de permission
# =====================================================================

def EstUnDes(*roles):
    """
    Fabrique une permission n'autorisant que les rôles donnés.

    Utilisation : `permission_classes = [EstUnDes(RH, ADMINISTRATEUR)]`
    """
    autorises = tuple(roles)

    class _PermissionRole(BasePermission):
        message = "Votre rôle ne permet pas cette action."

        def has_permission(self, request, view):
            return bool(
                request.user
                and request.user.is_authenticated
                and request.user.role in autorises
            )

    _PermissionRole.__name__ = "Est" + "Ou".join(r.title() for r in autorises)
    _PermissionRole.roles_autorises = autorises
    return _PermissionRole


def LectureTousEcriture(*roles):
    """
    Lecture ouverte à tout utilisateur authentifié, écriture réservée aux
    rôles donnés — le cas des référentiels (filiales, services, salles) que
    tout le monde consulte mais que peu de gens modifient.
    """
    autorises = tuple(roles)

    class _PermissionLectureEcriture(BasePermission):
        message = "Votre rôle ne permet pas de modifier cette ressource."

        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            if request.method in SAFE_METHODS:
                return True
            return request.user.role in autorises

    _PermissionLectureEcriture.roles_autorises = autorises
    return _PermissionLectureEcriture


# Permissions nommées, conservées telles quelles : elles sont référencées
# par les modules existants (journalisation, utilisateurs, salles, filiales).
EstAdministrateur = EstUnDes(ADMINISTRATEUR)
EstSecretaire = EstUnDes(SECRETAIRE)
EstDirecteur = EstUnDes(DIRECTEUR)
EstDirection = EstUnDes(*DIRECTION)
LectureSeulePourTous = LectureTousEcriture(ADMINISTRATEUR, SECRETAIRE)

#: Chef de service, Directeur ou Administrateur — gestion des stocks et des contrats.
GereLesStocks = EstUnDes(CHEF_SERVICE, DIRECTEUR, ADMINISTRATEUR)
GereLesContrats = EstUnDes(CHEF_SERVICE, DIRECTEUR, ADMINISTRATEUR)
#: Comptable, Directeur ou Administrateur — consultation des rapports administratifs.
GereLesRapports = EstUnDes(COMPTABLE, DIRECTEUR, ADMINISTRATEUR)


# =====================================================================
# Périmètre de données
# =====================================================================

def restreindre_a_la_filiale(queryset, utilisateur, champ="filiale"):
    """
    Restreint un queryset au périmètre visible par `utilisateur` :

    - direction (administrateur, DG) : tout le groupe ;
    - tout autre rôle : sa seule filiale ;
    - compte sans filiale : rien du tout.

    Ce filtrage n'est pas qu'un confort d'affichage : c'est lui qui assure
    l'étanchéité entre filiales. Les contrôles de rôle des actions (viser,
    valider…) portent sur le rôle seul et laisseraient passer le bon rôle
    d'une autre entreprise du groupe — c'est le périmètre du queryset qui
    rend l'objet introuvable avant d'en arriver là.
    """
    if est_direction(utilisateur):
        return queryset

    if not (utilisateur and utilisateur.is_authenticated):
        return queryset.none()

    filiale_id = getattr(utilisateur, "filiale_id", None)
    if filiale_id is None:
        return queryset.none()

    return queryset.filter(**{f"{champ}_id": filiale_id})


def restreindre_au_service(queryset, utilisateur, champ="service"):
    """
    Restreint un queryset au service de l'utilisateur.

    - direction : tout le groupe ;
    - chef de service : les services qu'il dirige, plus le sien ;
    - tout autre rôle : son seul service ;
    - compte sans service : rien du tout.
    """
    if est_direction(utilisateur):
        return queryset

    if not (utilisateur and utilisateur.is_authenticated):
        return queryset.none()

    services = set()
    if getattr(utilisateur, "service_id", None) is not None:
        services.add(utilisateur.service_id)
    if utilisateur.role == CHEF_SERVICE:
        services.update(
            utilisateur.services_diriges.values_list("pk", flat=True)
        )

    if not services:
        return queryset.none()

    return queryset.filter(**{f"{champ}_id__in": services})
