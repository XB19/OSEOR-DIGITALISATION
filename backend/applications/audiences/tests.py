from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from applications.filiales.models import Filiale
from applications.audiences.models import Audience
from applications.journalisation.models import JournalAction

User = get_user_model()


class AudienceTests(APITestCase):
    def setUp(self):
        self.kapi = Filiale.objects.create(nom="KAPI", code="KAPI")
        self.secretaire = User.objects.create_user(
            "sec", password="x", role=User.Role.SECRETAIRE, filiale=self.kapi)
        self.dg = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi,
            email="dg@oseor.com")

    def _creer_audience(self, lieu="Bureau du DG", salle=None):
        self.client.force_authenticate(self.secretaire)
        return self.client.post("/api/audiences/", {
            "nom": "Diallo", "prenom": "Awa", "profession": "Cliente",
            "contact": "0700", "objet_visite": "Partenariat", "dg": self.dg.id,
            "date_souhaitee": "2030-05-10", "heure_debut": "10:00", "heure_fin": "10:30",
            "lieu": lieu, "salle": salle,
        }, format="json")

    def test_audience_sans_salle(self):
        """RG-10 révisée : une audience peut se tenir dans un bureau (sans salle)."""
        rep = self._creer_audience(lieu="Bureau du DG", salle=None)
        self.assertEqual(rep.status_code, 201)
        self.assertIsNone(rep.data["salle"])
        self.assertEqual(rep.data["lieu"], "Bureau du DG")
        self.assertEqual(rep.data["statut"], "SAISIE")

    def test_validation_dg_sans_salle_ne_cree_pas_reservation(self):
        rep = self._creer_audience(lieu="Bureau du DG", salle=None)
        aud_id = rep.data["id"]
        self.client.force_authenticate(self.dg)
        rep2 = self.client.post(f"/api/audiences/{aud_id}/valider_dg/")
        self.assertEqual(rep2.status_code, 200)
        self.assertEqual(rep2.data["statut"], "VALIDEE_DG")
        self.assertIsNone(rep2.data["reservation"])

    def test_validation_dg_journalisee(self):
        """EF-20 : la validation d'une audience est tracée dans le journal."""
        rep = self._creer_audience()
        aud_id = rep.data["id"]
        self.client.force_authenticate(self.dg)
        self.client.post(f"/api/audiences/{aud_id}/valider_dg/")
        self.assertTrue(
            JournalAction.objects.filter(
                action="AUDIENCE_VALIDEE_DG", objet_id=aud_id).exists()
        )


class JournalAccesTests(APITestCase):
    def setUp(self):
        self.kapi = Filiale.objects.create(nom="KAPI", code="KAPI")
        self.admin = User.objects.create_user(
            "admin", password="x", role=User.Role.ADMINISTRATEUR)
        self.employe = User.objects.create_user(
            "emp", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)

    def test_journal_reserve_admin(self):
        self.client.force_authenticate(self.employe)
        self.assertEqual(self.client.get("/api/journal/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/journal/").status_code, 200)
