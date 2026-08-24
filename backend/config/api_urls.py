"""Routeur principal de l'API REST OSEOR Digitalisation."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from applications.utilisateurs.api import (
    UtilisateurViewSet, MoiView, ParametreLDAPView, TesterConnexionLDAPView,
)
from applications.filiales.api import FilialeViewSet, ServiceViewSet
from applications.salles.api import SalleViewSet
from applications.reservations.api import ReservationViewSet, SerieRecurrenceViewSet
from applications.audiences.api import AudienceViewSet, DelegationViewSet
from applications.notifications.api import NotificationViewSet
from applications.journalisation.api import JournalActionViewSet
from applications.tableau_bord.api import StatistiquesView
from applications.documents.api import DocumentViewSet
from applications.conges.api import DemandeCongeViewSet, JourFerieViewSet
from applications.evenements.api import EvenementViewSet
from applications.galerie.api import AlbumViewSet, PhotoViewSet
from applications.prestations.api import (
    JalonPrestationViewSet, PrestationViewSet,
)
from applications.notes.api import NoteRecueViewSet

router = DefaultRouter()
router.register("utilisateurs", UtilisateurViewSet, basename="utilisateur")
router.register("filiales", FilialeViewSet, basename="filiale")
router.register("services", ServiceViewSet, basename="service")
router.register("salles", SalleViewSet, basename="salle")
router.register("reservations", ReservationViewSet, basename="reservation")
router.register("series-recurrence", SerieRecurrenceViewSet, basename="serie")
router.register("audiences", AudienceViewSet, basename="audience")
router.register("delegations", DelegationViewSet, basename="delegation")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("journal", JournalActionViewSet, basename="journal")
router.register("documents", DocumentViewSet, basename="document")
router.register("evenements", EvenementViewSet, basename="evenement")
router.register("conges", DemandeCongeViewSet, basename="conge")
router.register("jours-feries", JourFerieViewSet, basename="jour-ferie")
router.register("albums", AlbumViewSet, basename="album")
router.register("photos", PhotoViewSet, basename="photo")
router.register("prestations", PrestationViewSet, basename="prestation")
router.register("jalons", JalonPrestationViewSet, basename="jalon")
router.register("notes-recues", NoteRecueViewSet, basename="note-recue")

urlpatterns = [
    # Authentification JWT (dev)
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MoiView.as_view(), name="auth_me"),

    path("parametres/ldap/", ParametreLDAPView.as_view(), name="parametres_ldap"),
    path("parametres/ldap/tester/", TesterConnexionLDAPView.as_view(), name="parametres_ldap_tester"),

    path("tableau-bord/stats/", StatistiquesView.as_view(), name="tableau_bord_stats"),

    path("", include(router.urls)),
]
