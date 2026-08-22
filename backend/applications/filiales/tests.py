"""
Organigramme : services, rattachement des utilisateurs et chaîne
hiérarchique. Ces règles conditionnent les validations « chef de service »
et la chaîne de validation des congés.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase
from rest_framework.test import APITestCase

from applications.filiales.models import Filiale, Service

User = get_user_model()


class BaseOrganigramme:
    """Deux filiales, un service par filiale, une hiérarchie sur trois niveaux."""

    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")

        self.compta = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.kapi)
        self.compta_oseor = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.oseor)

        # dg -> chef -> employe
        self.dg = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.chef = User.objects.create_user(
            "chef", password="x", role=User.Role.CHEF_SERVICE, filiale=self.kapi,
            service=self.compta, responsable_hierarchique=self.dg)
        self.employe = User.objects.create_user(
            "employe", password="x", role=User.Role.EMPLOYE, filiale=self.kapi,
            service=self.compta, responsable_hierarchique=self.chef)

        self.compta.chef = self.chef
        self.compta.save()


class ServiceTests(BaseOrganigramme, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_meme_code_autorise_dans_deux_filiales(self):
        """Chaque entreprise du groupe a son propre service « COMPTA »."""
        self.assertEqual(self.compta.code, self.compta_oseor.code)
        self.assertNotEqual(self.compta.filiale_id, self.compta_oseor.filiale_id)

    def test_code_unique_dans_une_meme_filiale(self):
        with self.assertRaises(IntegrityError):
            Service.objects.create(nom="Compta bis", code="COMPTA", filiale=self.kapi)

    def test_chef_doit_appartenir_a_la_filiale_du_service(self):
        etranger = User.objects.create_user(
            "etranger", password="x", role=User.Role.CHEF_SERVICE, filiale=self.oseor)
        service = Service(nom="Moyens Généraux", code="MG",
                          filiale=self.kapi, chef=etranger)
        with self.assertRaises(ValidationError):
            service.full_clean()

    def test_membres_du_service(self):
        self.assertCountEqual(
            list(self.compta.membres.all()), [self.chef, self.employe])

    def test_service_supprime_ne_supprime_pas_ses_membres(self):
        """SET_NULL : perdre son service ne doit jamais effacer un compte."""
        self.compta_oseor.delete()
        self.employe.refresh_from_db()
        self.assertTrue(User.objects.filter(pk=self.employe.pk).exists())


class HierarchieTests(BaseOrganigramme, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_chaine_du_plus_proche_au_plus_lointain(self):
        self.assertEqual(
            [u.username for u in self.employe.chaine_responsables()],
            ["chef", "dg"],
        )

    def test_chaine_vide_au_sommet(self):
        self.assertEqual(self.dg.chaine_responsables(), [])

    def test_responsable_transitif(self):
        self.assertTrue(self.chef.est_responsable_de(self.employe))
        self.assertTrue(self.dg.est_responsable_de(self.employe))
        self.assertFalse(self.employe.est_responsable_de(self.chef))

    def test_nul_n_est_son_propre_responsable(self):
        self.assertFalse(self.employe.est_responsable_de(self.employe))

    def test_cycle_direct_refuse(self):
        self.dg.responsable_hierarchique = self.dg
        with self.assertRaises(ValidationError):
            self.dg.full_clean()

    def test_cycle_indirect_refuse(self):
        """dg -> employe fermerait la boucle employe -> chef -> dg."""
        self.dg.responsable_hierarchique = self.employe
        with self.assertRaises(ValidationError):
            self.dg.full_clean()

    def test_cycle_existant_ne_boucle_pas_a_l_infini(self):
        """
        Un cycle introduit hors validation (fixture, LDAP, SQL direct) ne doit
        pas figer la remontée de hiérarchie.
        """
        User.objects.filter(pk=self.dg.pk).update(
            responsable_hierarchique=self.employe)
        self.dg.refresh_from_db()

        chaine = self.employe.chaine_responsables()

        self.assertLessEqual(len(chaine), User.PROFONDEUR_MAX_HIERARCHIE)
        self.assertNotIn(self.employe.pk, [u.pk for u in chaine])


class ValideurCongeTests(BaseOrganigramme, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_responsable_direct_prioritaire(self):
        self.assertEqual(self.employe.valideur_conge, self.chef)

    def test_repli_sur_le_chef_de_service(self):
        self.employe.responsable_hierarchique = None
        self.employe.save()
        self.assertEqual(self.employe.valideur_conge, self.chef)

    def test_le_chef_ne_se_valide_pas_lui_meme(self):
        """Sans responsable, le chef d'un service ne devient pas son propre valideur."""
        self.chef.responsable_hierarchique = None
        self.chef.save()
        self.assertIsNone(self.chef.valideur_conge)

    def test_aucun_valideur_sans_rattachement(self):
        isole = User.objects.create_user(
            "isole", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)
        self.assertIsNone(isole.valideur_conge)


class ServiceAPITests(BaseOrganigramme, APITestCase):
    """Endpoint /api/services/ — consommé par les listes déroulantes du frontend."""

    def setUp(self):
        self.creer_donnees()

    def test_lecture_ouverte_a_tout_utilisateur_connecte(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.get("/api/services/")
        self.assertEqual(reponse.status_code, 200)

    def test_anonyme_refuse(self):
        self.assertIn(self.client.get("/api/services/").status_code, (401, 403))

    def test_filtre_par_filiale(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.get(f"/api/services/?filiale={self.kapi.pk}")
        resultats = reponse.data.get("results", reponse.data)
        self.assertEqual([s["id"] for s in resultats], [self.compta.pk])

    def test_employe_ne_peut_pas_creer(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.post("/api/services/", {
            "nom": "Informatique", "code": "IT", "filiale": self.kapi.pk,
        })
        self.assertEqual(reponse.status_code, 403)

    def test_administrateur_peut_creer(self):
        admin = User.objects.create_user(
            "admin2", password="x", role=User.Role.ADMINISTRATEUR, filiale=self.kapi)
        self.client.force_authenticate(admin)
        reponse = self.client.post("/api/services/", {
            "nom": "Informatique", "code": "IT", "filiale": self.kapi.pk,
        })
        self.assertEqual(reponse.status_code, 201)

    def test_expose_chef_et_effectif(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.get(f"/api/services/{self.compta.pk}/")
        self.assertEqual(reponse.data["chef_nom"], self.chef.nom_complet)
        self.assertEqual(reponse.data["nb_membres"], 2)
