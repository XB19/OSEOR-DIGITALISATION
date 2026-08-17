"""Permissions DRF basées sur les rôles métier OSEOR."""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class EstAdministrateur(BasePermission):
    """Administrateur principal du groupe."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "ADMINISTRATEUR"
        )


class EstSecretaire(BasePermission):
    """Secrétaire / assistante de direction."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "SECRETAIRE"
        )


class EstDirecteur(BasePermission):
    """Directeur (DG)."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "DIRECTEUR"
        )


class LectureSeulePourTous(BasePermission):
    """
    Lecture autorisée à tout utilisateur authentifié ;
    écriture réservée aux administrateurs et secrétaires.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in ("ADMINISTRATEUR", "SECRETAIRE")
