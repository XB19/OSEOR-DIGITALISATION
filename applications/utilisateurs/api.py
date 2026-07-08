from django.contrib.auth import get_user_model
from rest_framework import viewsets, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import EstAdministrateur
from applications.journalisation.services import enregistrer_action
from .serializers import (
    UtilisateurSerializer,
    UtilisateurEcritureSerializer,
    MoiSerializer,
)

User = get_user_model()


class UtilisateurViewSet(viewsets.ModelViewSet):
    """
    Gestion des utilisateurs (annuaire + administration).

    - Lecture : tout utilisateur authentifié (sert à l'annuaire, la
      délégation, la liste de présence interne).
    - Écriture : administrateur uniquement.
    """

    queryset = User.objects.select_related("filiale").all()
    filterset_fields = ("role", "filiale", "actif")
    search_fields = ("first_name", "last_name", "username", "email")
    ordering_fields = ("last_name", "first_name")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return UtilisateurEcritureSerializer
        return UtilisateurSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [EstAdministrateur()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        u = serializer.save()
        enregistrer_action(
            self.request.user, "UTILISATEUR_CREE",
            f"{u.nom_complet} ({u.get_role_display()})", objet=u,
        )

    def perform_update(self, serializer):
        u = serializer.save()
        enregistrer_action(
            self.request.user, "UTILISATEUR_MODIFIE",
            f"{u.nom_complet} ({u.get_role_display()})", objet=u,
        )

    @action(detail=False, methods=["post"], permission_classes=[EstAdministrateur])
    def synchroniser_ad(self, request):
        """
        Synchronise les utilisateurs depuis l'Active Directory local via LDAP.
        Nécessite LDAP_SERVER_URI / LDAP_BIND_DN / LDAP_BIND_PASSWORD dans .env.
        """
        from django.conf import settings
        from .services_ad import lister_utilisateurs_ad, synchroniser_utilisateur_ad

        if not getattr(settings, 'LDAP_SERVER_URI', ''):
            return Response(
                {'detail': 'Active Directory non configuré dans .env '
                           '(LDAP_SERVER_URI, LDAP_BIND_DN, LDAP_BIND_PASSWORD, LDAP_BASE_DN).'},
                status=400,
            )

        try:
            ad_entries = lister_utilisateurs_ad()
        except Exception as exc:
            return Response(
                {'detail': f'Erreur de connexion à l\'Active Directory : {exc}'},
                status=502,
            )

        crees = mis_a_jour = ignores = 0
        for entry in ad_entries:
            resultat = synchroniser_utilisateur_ad(entry)
            if resultat == 'cree':
                crees += 1
            elif resultat == 'mis_a_jour':
                mis_a_jour += 1
            else:
                ignores += 1

        enregistrer_action(
            request.user, 'SYNCHRO_AD',
            f'AD local : {crees} créés, {mis_a_jour} mis à jour, {ignores} ignorés',
        )
        return Response({
            'crees':      crees,
            'mis_a_jour': mis_a_jour,
            'ignores':    ignores,
            'total_ad':   len(ad_entries),
        })

    @action(detail=False, methods=["get"])
    def recherche(self, request):
        """
        Recherche d'utilisateurs pour la délégation (EF-14) :
        ex. ?q=paul -> renvoie les correspondances nom/prénom/email.
        """
        q = request.query_params.get("q", "").strip()
        qs = self.get_queryset().filter(is_active=True)
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(username__icontains=q)
            )
        qs = qs[:20]
        return Response(UtilisateurSerializer(qs, many=True).data)


class MoiView(generics.RetrieveAPIView):
    """Profil de l'utilisateur connecté."""

    serializer_class = MoiSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
