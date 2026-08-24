"""
Annuaire des utilisateurs : ce qui est exposé, et à qui.

`/api/utilisateurs/` est lisible par TOUT utilisateur authentifié. Les
champs qui y figurent sont donc visibles de tout le groupe — d'où ces
tests, qui verrouillent ce qui ne doit pas s'y trouver.
"""

from datetime import date

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from applications.filiales.models import Filiale

User = get_user_model()

#: Données RH : ni l'âge ni l'ancienneté d'un collègue n'ont leur place
#: dans un trombinoscope ouvert à tous.
CHAMPS_CONFIDENTIELS = ("date_naissance", "date_embauche")


class AnnuaireTests(APITestCase):
    def setUp(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.employe = User.objects.create_user(
            "employe", password="x", role=User.Role.EMPLOYE, filiale=self.kapi,
            date_naissance=date(1990, 3, 15), date_embauche=date(2020, 1, 6))
        self.collegue = User.objects.create_user(
            "collegue", password="x", role=User.Role.EMPLOYE, filiale=self.kapi,
            date_naissance=date(1985, 7, 2), date_embauche=date(2019, 4, 1))

    def test_annuaire_ne_divulgue_pas_les_donnees_rh(self):
        self.client.force_authenticate(self.employe)

        reponse = self.client.get("/api/utilisateurs/")
        resultats = reponse.data.get("results", reponse.data)

        self.assertTrue(resultats)
        for fiche in resultats:
            for champ in CHAMPS_CONFIDENTIELS:
                self.assertNotIn(champ, fiche)

    def test_detail_d_un_collegue_non_plus(self):
        self.client.force_authenticate(self.employe)

        reponse = self.client.get(f"/api/utilisateurs/{self.collegue.pk}/")

        for champ in CHAMPS_CONFIDENTIELS:
            self.assertNotIn(champ, reponse.data)

    def test_chacun_voit_ses_propres_dates(self):
        """Sur son propre profil, en revanche, l'intéressé y a accès."""
        self.client.force_authenticate(self.employe)

        reponse = self.client.get("/api/auth/me/")

        self.assertEqual(reponse.data["date_naissance"], "1990-03-15")
        self.assertEqual(reponse.data["date_embauche"], "2020-01-06")

    def test_ecriture_reservee_a_l_administrateur(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.patch(
            f"/api/utilisateurs/{self.collegue.pk}/",
            {"date_embauche": "2015-01-01"}, format="json")
        self.assertEqual(reponse.status_code, 403)

    def test_administrateur_renseigne_les_dates_rh(self):
        admin = User.objects.create_user(
            "admin", password="x", role=User.Role.ADMINISTRATEUR, filiale=self.kapi)
        self.client.force_authenticate(admin)

        reponse = self.client.patch(
            f"/api/utilisateurs/{self.collegue.pk}/",
            {"date_embauche": "2015-01-01"}, format="json")

        self.assertEqual(reponse.status_code, 200)
        self.collegue.refresh_from_db()
        self.assertEqual(self.collegue.date_embauche, date(2015, 1, 1))
