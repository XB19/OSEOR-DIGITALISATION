"""
Prestations de services : périmètre par service, pilotage et avancement
mesuré sur les jalons.

Le périmètre est le point sensible : un chef de service ne doit pas voir
les dossiers du service voisin, mais un intervenant doit voir la prestation
sur laquelle il travaille, même hors de son service.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from applications.filiales.models import Filiale, Service
from applications.prestations import services
from applications.prestations.models import JalonPrestation, Prestation

User = get_user_model()


class BasePrestations:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")

        self.conseil = Service.objects.create(
            nom="Conseil", code="CONS", filiale=self.kapi)
        self.audit = Service.objects.create(
            nom="Audit", code="AUD", filiale=self.kapi)

        self.directeur = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)

        self.chef_conseil = User.objects.create_user(
            "chef_conseil", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.conseil)
        self.conseil.chef = self.chef_conseil
        self.conseil.save()

        self.chef_audit = User.objects.create_user(
            "chef_audit", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.audit)
        self.audit.chef = self.chef_audit
        self.audit.save()

        self.consultant = User.objects.create_user(
            "consultant", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.conseil)
        self.auditeur = User.objects.create_user(
            "auditeur", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.audit)

    def creer_prestation(self, **surcharges):
        donnees = {
            "reference": f"KAPI-PRS-2026-{Prestation.objects.count() + 1:04d}",
            "intitule": "Audit organisationnel",
            "client": "Société Alpha",
            "filiale": self.kapi,
            "service": self.conseil,
            "responsable": self.chef_conseil,
            "date_debut": date(2027, 1, 11),
            "date_fin_prevue": date(2027, 3, 31),
            "montant": Decimal("4500000"),
        }
        donnees.update(surcharges)
        return Prestation.objects.create(**donnees)


class ValidationTests(BasePrestations, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_fin_prevue_avant_debut_refusee(self):
        prestation = Prestation(
            reference="X", intitule="Incohérente", client="Alpha",
            filiale=self.kapi, service=self.conseil,
            responsable=self.chef_conseil,
            date_debut=date(2027, 3, 31), date_fin_prevue=date(2027, 1, 11))
        with self.assertRaises(ValidationError):
            prestation.full_clean()

    def test_service_d_une_autre_filiale_refuse(self):
        service_oseor = Service.objects.create(
            nom="Conseil OSEOR", code="CONS", filiale=self.oseor)
        prestation = Prestation(
            reference="X", intitule="Incohérente", client="Alpha",
            filiale=self.kapi, service=service_oseor,
            responsable=self.chef_conseil,
            date_debut=date(2027, 1, 11), date_fin_prevue=date(2027, 3, 31))
        with self.assertRaises(ValidationError):
            prestation.full_clean()

    def test_en_retard_calcule(self):
        """Un drapeau « en retard » stocké serait faux dès le lendemain."""
        depassee = self.creer_prestation(
            date_debut=date(2020, 1, 1), date_fin_prevue=date(2020, 3, 1))
        self.assertTrue(depassee.en_retard)

    def test_prestation_close_jamais_en_retard(self):
        close = self.creer_prestation(
            date_debut=date(2020, 1, 1), date_fin_prevue=date(2020, 3, 1),
            statut=Prestation.Statut.TERMINEE)
        self.assertFalse(close.en_retard)

    def test_prestation_a_venir_pas_en_retard(self):
        future = self.creer_prestation(
            date_debut=timezone.localdate() + timedelta(days=10),
            date_fin_prevue=timezone.localdate() + timedelta(days=40))
        self.assertFalse(future.en_retard)


class PerimetreTests(BasePrestations, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.prestation_conseil = self.creer_prestation(
            intitule="Mission Conseil", service=self.conseil,
            responsable=self.chef_conseil)
        self.prestation_audit = self.creer_prestation(
            intitule="Mission Audit", service=self.audit,
            responsable=self.chef_audit)

    def _intitules(self, utilisateur):
        return set(
            services.prestations_visibles(utilisateur).values_list(
                "intitule", flat=True))

    def test_direction_voit_tout(self):
        self.assertEqual(
            self._intitules(self.directeur),
            {"Mission Conseil", "Mission Audit"},
        )

    def test_membre_limite_a_son_service(self):
        self.assertEqual(self._intitules(self.consultant), {"Mission Conseil"})

    def test_chef_ne_voit_pas_le_service_voisin(self):
        self.assertEqual(self._intitules(self.chef_conseil), {"Mission Conseil"})

    def test_intervenant_voit_sa_prestation_hors_de_son_service(self):
        """On ne cache pas à quelqu'un le travail qu'il fait."""
        self.prestation_audit.intervenants.add(self.consultant)

        self.assertIn("Mission Audit", self._intitules(self.consultant))

    def test_sans_service_ne_voit_que_ses_prestations(self):
        isole = User.objects.create_user(
            "isole", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)
        self.assertEqual(self._intitules(isole), set())

        self.prestation_conseil.intervenants.add(isole)
        self.assertEqual(self._intitules(isole), {"Mission Conseil"})

    def test_pas_de_doublon_quand_plusieurs_criteres_coincident(self):
        """Responsable ET membre du service : la prestation ne sort qu'une fois."""
        self.prestation_conseil.intervenants.add(self.chef_conseil)

        resultat = services.prestations_visibles(self.chef_conseil)

        self.assertEqual(resultat.count(), 1)


class PilotageTests(BasePrestations, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.prestation = self.creer_prestation(
            responsable=self.consultant, service=self.conseil)

    def test_responsable_pilote(self):
        self.assertTrue(services.peut_modifier(self.prestation, self.consultant))

    def test_chef_du_service_pilote(self):
        self.assertTrue(
            services.peut_modifier(self.prestation, self.chef_conseil))

    def test_direction_pilote(self):
        self.assertTrue(services.peut_modifier(self.prestation, self.directeur))

    def test_chef_d_un_autre_service_ne_pilote_pas(self):
        self.assertFalse(services.peut_modifier(self.prestation, self.chef_audit))

    def test_simple_intervenant_ne_pilote_pas(self):
        self.prestation.intervenants.add(self.auditeur)
        self.assertFalse(services.peut_modifier(self.prestation, self.auditeur))


class AvancementTests(BasePrestations, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.prestation = self.creer_prestation()

    def test_sans_jalon_renvoie_none(self):
        """
        « Aucun jalon défini » n'est pas « rien de fait » : les confondre
        ferait passer un dossier avancé pour un dossier à l'arrêt.
        """
        self.assertIsNone(services.avancement(self.prestation))

    def test_pourcentage_sur_les_jalons(self):
        for index in range(4):
            JalonPrestation.objects.create(
                prestation=self.prestation, intitule=f"Étape {index}",
                date_prevue=date(2027, 2, 1 + index),
                date_realisation=date(2027, 2, 1) if index < 1 else None)

        resultat = services.avancement(self.prestation)

        self.assertEqual(resultat["jalons"], 4)
        self.assertEqual(resultat["realises"], 1)
        self.assertEqual(resultat["pourcentage"], 25)

    def test_prochain_jalon(self):
        JalonPrestation.objects.create(
            prestation=self.prestation, intitule="Cadrage",
            date_prevue=date(2027, 1, 15), date_realisation=date(2027, 1, 15))
        JalonPrestation.objects.create(
            prestation=self.prestation, intitule="Restitution",
            date_prevue=date(2027, 3, 20))

        self.assertEqual(services.avancement(self.prestation)["prochain"],
                         "Restitution")

    def test_jalons_en_retard(self):
        JalonPrestation.objects.create(
            prestation=self.prestation, intitule="Dépassé",
            date_prevue=date(2020, 1, 15))

        self.assertEqual(
            services.avancement(self.prestation)["jalons_en_retard"], 1)

    def test_tout_realise(self):
        JalonPrestation.objects.create(
            prestation=self.prestation, intitule="Unique",
            date_prevue=date(2027, 1, 15), date_realisation=date(2027, 1, 15))

        resultat = services.avancement(self.prestation)
        self.assertEqual(resultat["pourcentage"], 100)
        self.assertIsNone(resultat["prochain"])


class PrestationAPITests(BasePrestations, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_creation_genere_la_reference_et_deduit_la_filiale(self):
        self.client.force_authenticate(self.chef_conseil)

        reponse = self.client.post("/api/prestations/", {
            "intitule": "Mission Beta",
            "client": "Société Beta",
            "service": self.conseil.pk,
            "responsable": self.consultant.pk,
            "date_debut": "2027-01-11",
            "date_fin_prevue": "2027-03-31",
            "montant": "1500000",
        }, format="json")

        self.assertEqual(reponse.status_code, 201)
        prestation = Prestation.objects.get(intitule="Mission Beta")
        self.assertTrue(prestation.reference.startswith("KAPI-PRS-"))
        self.assertEqual(prestation.filiale, self.kapi)

    def test_dates_incoherentes_refusees(self):
        self.client.force_authenticate(self.chef_conseil)
        reponse = self.client.post("/api/prestations/", {
            "intitule": "Incohérente", "client": "Alpha",
            "service": self.conseil.pk, "responsable": self.consultant.pk,
            "date_debut": "2027-03-31", "date_fin_prevue": "2027-01-11",
        }, format="json")
        self.assertEqual(reponse.status_code, 400)

    def test_chef_voisin_ne_modifie_pas(self):
        prestation = self.creer_prestation()
        self.client.force_authenticate(self.chef_audit)

        reponse = self.client.patch(
            f"/api/prestations/{prestation.pk}/",
            {"intitule": "Détournée"}, format="json")

        self.assertIn(reponse.status_code, (403, 404))

    def test_cloture_pose_la_date_reelle(self):
        prestation = self.creer_prestation()
        self.client.force_authenticate(self.chef_conseil)

        reponse = self.client.post(f"/api/prestations/{prestation.pk}/cloturer/")

        self.assertEqual(reponse.status_code, 200)
        prestation.refresh_from_db()
        self.assertEqual(prestation.statut, Prestation.Statut.TERMINEE)
        self.assertEqual(prestation.date_fin_reelle, timezone.localdate())

    def test_cloture_deux_fois_refusee(self):
        prestation = self.creer_prestation()
        self.client.force_authenticate(self.chef_conseil)

        self.client.post(f"/api/prestations/{prestation.pk}/cloturer/")
        reponse = self.client.post(f"/api/prestations/{prestation.pk}/cloturer/")

        self.assertEqual(reponse.status_code, 400)

    def test_tableau_de_bord(self):
        self.creer_prestation(statut=Prestation.Statut.EN_COURS)
        self.creer_prestation(
            date_debut=date(2020, 1, 1), date_fin_prevue=date(2020, 3, 1))

        self.client.force_authenticate(self.chef_conseil)
        reponse = self.client.get("/api/prestations/tableau_de_bord/")

        self.assertEqual(reponse.data["total"], 2)
        self.assertEqual(len(reponse.data["en_retard"]), 1)

    def test_jalon_pointe_realise(self):
        prestation = self.creer_prestation()
        jalon = JalonPrestation.objects.create(
            prestation=prestation, intitule="Cadrage", date_prevue=date(2027, 1, 15))

        self.client.force_authenticate(self.chef_conseil)
        reponse = self.client.post(f"/api/jalons/{jalon.pk}/realiser/")

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data["realise"])

    def test_jalon_non_pilote_refuse(self):
        prestation = self.creer_prestation()
        jalon = JalonPrestation.objects.create(
            prestation=prestation, intitule="Cadrage", date_prevue=date(2027, 1, 15))

        self.client.force_authenticate(self.consultant)
        reponse = self.client.post(f"/api/jalons/{jalon.pk}/realiser/")

        self.assertEqual(reponse.status_code, 403)

    def test_anonyme_refuse(self):
        self.assertIn(self.client.get("/api/prestations/").status_code, (401, 403))
