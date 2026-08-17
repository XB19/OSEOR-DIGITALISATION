"""
Intégration Azure AD / Entra ID via OIDC.

Flux :
  1. L'utilisateur clique "Se connecter avec Microsoft" dans Angular
  2. Django redirige vers le portail Azure (GET /oidc/authenticate/)
  3. Azure authentifie l'utilisateur et renvoie un code (POST /oidc/callback/)
  4. Ce backend crée/met à jour l'Utilisateur OSEOR depuis les claims Azure
  5. La vue callback émet un JWT simplejwt et redirige vers Angular

Configuration requise dans .env :
  AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
"""

from mozilla_django_oidc.auth import OIDCAuthenticationBackend


# ---------------------------------------------------------------------------
# Mapping groupes Azure AD → rôles OSEOR
# Adapter les noms de groupes selon votre configuration Entra ID.
# Dans Azure : App registrations → Token configuration → Add groups claim
# ---------------------------------------------------------------------------
GROUPES_ROLES = {
    # Nom du groupe AD       : rôle OSEOR correspondant
    'OSEOR-Administrateurs': 'ADMINISTRATEUR',
    'OSEOR-DG':              'DIRECTEUR',
    'OSEOR-Secretariat':     'SECRETAIRE',
    'OSEOR-RH':              'RH',
    'OSEOR-Comptabilite':    'COMPTABLE',
    'OSEOR-Chefs-Service':   'CHEF_SERVICE',
}

# Mapping jobTitle AD (mots-clés) → rôle OSEOR — fallback si pas de groupes
TITRES_ROLES = {
    'directeur':   'DIRECTEUR',
    'director':    'DIRECTEUR',
    'secrétaire':  'SECRETAIRE',
    'secretaire':  'SECRETAIRE',
    'secretary':   'SECRETAIRE',
    'assistante':  'SECRETAIRE',
    'rh':          'RH',
    'ressources humaines': 'RH',
    'comptable':   'COMPTABLE',
    'comptabilité': 'COMPTABLE',
    'chef de service': 'CHEF_SERVICE',
}


def generer_username(email: str) -> str:
    """
    Génère un username unique depuis l'email AD.
    Ex : paulin.tcheouafe@oseor.com → paulin.tcheouafe
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    base = email.split('@')[0].lower().replace(' ', '.')
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"
        n += 1
    return username


class OseorOIDCBackend(OIDCAuthenticationBackend):
    """
    Backend OIDC personnalisé OSEOR.
    - Cherche l'utilisateur par email (preferred_username Azure)
    - Crée ou met à jour l'Utilisateur OSEOR
    - Mappe les groupes/titres AD vers les rôles OSEOR
    - Mappe le département AD vers la filiale OSEOR (si configuré)
    """

    def filter_users_by_claims(self, claims):
        """Trouve l'Utilisateur OSEOR par email AD."""
        email = (claims.get('email') or claims.get('preferred_username', '')).lower()
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email__iexact=email)

    def create_user(self, claims):
        """Crée un nouvel Utilisateur OSEOR depuis les claims Azure AD."""
        user = super().create_user(claims)
        self._synchroniser(user, claims, creation=True)
        return user

    def update_user(self, user, claims):
        """Met à jour l'Utilisateur OSEOR à chaque connexion AD."""
        self._synchroniser(user, claims, creation=False)
        return user

    # ------------------------------------------------------------------
    # Synchronisation claims Azure → Utilisateur OSEOR
    # ------------------------------------------------------------------

    def _synchroniser(self, user, claims, creation=False):
        champs = []

        # Prénom / nom
        if claims.get('given_name'):
            user.first_name = claims['given_name']
            champs.append('first_name')
        if claims.get('family_name'):
            user.last_name = claims['family_name']
            champs.append('last_name')

        # Email (preferred_username sur Azure = UPN = adresse mail)
        email = claims.get('email') or claims.get('preferred_username', '')
        if email and not user.email:
            user.email = email.lower()
            champs.append('email')

        # Téléphone (attribut optionnel dans Azure, nécessite le scope User.Read)
        tel = claims.get('mobilePhone') or claims.get('telephoneNumber', '')
        if tel and not user.telephone:
            user.telephone = tel
            champs.append('telephone')

        # Rôle OSEOR depuis groupes AD (création uniquement, ou si encore EMPLOYE)
        if creation or user.role == 'EMPLOYE':
            role = self._detecter_role(claims)
            if role:
                user.role = role
                champs.append('role')

        # Filiale depuis département AD (optionnel)
        # Décommentez et adaptez si vos utilisateurs AD ont un département
        # département = claims.get('department', '')
        # if département and creation:
        #     from applications.filiales.models import Filiale
        #     try:
        #         filiale = Filiale.objects.get(nom__iexact=département)
        #         user.filiale = filiale
        #         champs.append('filiale')
        #     except Filiale.DoesNotExist:
        #         pass  # département inconnu → filiale reste None

        if champs:
            user.save(update_fields=champs)

    def _detecter_role(self, claims) -> str | None:
        """
        Détecte le rôle OSEOR depuis les claims Azure AD.

        Priorité :
          1. Groupes AD (groups claim — nécessite Token configuration dans Azure)
          2. jobTitle AD (fallback si pas de groupes configurés)
        """
        # 1. Via groupes AD (noms ou ObjectIDs selon la config Azure)
        groupes = claims.get('groups', [])
        for nom_groupe, role in GROUPES_ROLES.items():
            if nom_groupe in groupes:
                return role

        # 2. Via le titre de poste
        titre = claims.get('jobTitle', '').lower()
        for mot_cle, role in TITRES_ROLES.items():
            if mot_cle in titre:
                return role

        return 'EMPLOYE'  # rôle par défaut
