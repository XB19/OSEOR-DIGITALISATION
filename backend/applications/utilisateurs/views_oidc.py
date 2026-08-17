"""
Vue callback OIDC OSEOR.

Après que Azure AD a authentifié l'utilisateur et que le backend OIDC
a créé/mis à jour l'Utilisateur, cette vue :
  1. Émet une paire de tokens JWT (access + refresh) via simplejwt
  2. Redirige le navigateur vers Angular avec les tokens dans l'URL
  3. Angular les stocke dans localStorage et fonctionne normalement

En cas d'échec, redirige vers /connexion?erreur=sso_echec.
"""

from django.shortcuts import redirect
from django.conf import settings
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView
from rest_framework_simplejwt.tokens import RefreshToken


FRONTEND_URL_DEFAULT = 'http://localhost:4200'


class OseorOIDCCallbackView(OIDCAuthenticationCallbackView):

    def login_success(self):
        """L'utilisateur est authentifié : émettre le JWT et renvoyer vers Angular."""
        user = self.request.user
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        frontend = getattr(settings, 'FRONTEND_URL', FRONTEND_URL_DEFAULT)
        return redirect(
            f"{frontend}/auth/callback"
            f"?access={access_token}&refresh={refresh_token}"
        )

    def login_failure(self):
        """Échec d'authentification Azure : renvoyer vers la page de connexion."""
        frontend = getattr(settings, 'FRONTEND_URL', FRONTEND_URL_DEFAULT)
        return redirect(f"{frontend}/connexion?erreur=sso_echec")
