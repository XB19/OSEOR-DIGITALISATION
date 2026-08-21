"""
Documents administratifs : périmètre de lecture, création et chaîne de visas.

Tests de caractérisation écrits AVANT la centralisation des contrôles de rôle
(étape 2) : ils décrivent le comportement tel qu'il est aujourd'hui, pour que
le passage à `config/permissions.py` soit prouvé iso-fonctionnel.
"""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from applications.filiales.models import Filiale
from applications.documents.models import (
    ConfigurationDocument, Document, TypeDocument,
)

User = get_user_model()


class BaseDocuments:
    """Deux filiales, une chaîne de visas à trois étapes chez KAPI."""

    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")

        self.config = ConfigurationDocument.objects.create(
            filiale=self.kapi,
            type_document=TypeDocument.FICHE_BESOIN,
            colonnes=[{"cle": "motif", "libelle": "Besoin et motifs"}],
            visas=[
                {"cle": "demandeur", "libelle": "Visa du Demandeur"},
                {"cle": "comptable", "libelle": "Visa du Comptable", "role": "COMPTABLE"},
                {"cle": "dg", "libelle": "Visa du DG", "role": "DIRECTEUR"},
            ],
        )

        self.employe = User.objects.create_user(
            "employe", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)
        self.comptable = User.objects.create_user(
            "comptable", password="x", role=User.Role.COMPTABLE, filiale=self.kapi)
        self.comptable_oseor = User.objects.create_user(
            "comptable2", password="x", role=User.Role.COMPTABLE, filiale=self.oseor)
        self.directeur = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.admin = User.objects.create_user(
            "admin", password="x", role=User.Role.ADMINISTRATEUR, filiale=self.kapi)
        self.employe_oseor = User.objects.create_user(
            "employe2", password="x", role=User.Role.EMPLOYE, filiale=self.oseor)

    def creer_document(self, demandeur=None, filiale=None):
        demandeur = demandeur or self.employe
        filiale = filiale or self.kapi
        return Document.objects.create(
            filiale=filiale,
            type_document=TypeDocument.FICHE_BESOIN,
            demandeur=demandeur,
            numero=f"{filiale.code}-FB-2026-{Document.objects.count() + 1:04d}",
            lignes=[{"motif": "Ramettes A4"}],
            etape_visa_courante=1,
        )


class PerimetreLectureTests(BaseDocuments, APITestCase):
    def setUp(self):
        self.creer_donnees()
        self.doc_kapi = self.creer_document()
        self.doc_oseor = self.creer_document(
            demandeur=self.employe_oseor, filiale=self.oseor)

    def _numeros(self, reponse):
        resultats = reponse.data.get("results", reponse.data)
        return {d["numero"] for d in resultats}

    def test_administrateur_voit_tout_le_groupe(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self._numeros(self.client.get("/api/documents/")),
            {self.doc_kapi.numero, self.doc_oseor.numero},
        )

    def test_directeur_voit_tout_le_groupe(self):
        self.client.force_authenticate(self.directeur)
        self.assertEqual(
            self._numeros(self.client.get("/api/documents/")),
            {self.doc_kapi.numero, self.doc_oseor.numero},
        )

    def test_employe_limite_a_sa_filiale(self):
        self.client.force_authenticate(self.employe)
        self.assertEqual(
            self._numeros(self.client.get("/api/documents/")),
            {self.doc_kapi.numero},
        )

    def test_anonyme_refuse(self):
        self.assertIn(self.client.get("/api/documents/").status_code, (401, 403))

    def test_suppression_et_modification_indisponibles(self):
        """http_method_names limite l'API à get/post : un visa n'est jamais effacé."""
        self.client.force_authenticate(self.admin)
        url = f"/api/documents/{self.doc_kapi.pk}/"
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertEqual(self.client.put(url, {}).status_code, 405)


class CreationTests(BaseDocuments, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_filiale_deduite_du_demandeur(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.post("/api/documents/", {
            "type_document": TypeDocument.FICHE_BESOIN,
            "lignes": [{"motif": "Ramettes A4"}],
        }, format="json")
        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse.data["filiale"], self.kapi.pk)
        self.assertEqual(reponse.data["demandeur"], self.employe.pk)

    def test_numero_prefixe_par_le_code_filiale(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.post("/api/documents/", {
            "type_document": TypeDocument.FICHE_BESOIN,
        }, format="json")
        self.assertTrue(reponse.data["numero"].startswith("KAPI-FB-"))

    def test_visa_du_demandeur_appose_a_la_soumission(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.post("/api/documents/", {
            "type_document": TypeDocument.FICHE_BESOIN,
        }, format="json")
        self.assertEqual(len(reponse.data["historique_visas"]), 1)
        self.assertEqual(reponse.data["etape_visa_courante"], 1)
        self.assertEqual(reponse.data["statut"], Document.Statut.EN_COURS)

    def test_compte_sans_filiale_refuse(self):
        orphelin = User.objects.create_user(
            "orphelin", password="x", role=User.Role.EMPLOYE)
        self.client.force_authenticate(orphelin)
        reponse = self.client.post("/api/documents/", {
            "type_document": TypeDocument.FICHE_BESOIN,
        }, format="json")
        self.assertEqual(reponse.status_code, 400)

    def test_sans_chaine_de_visas_le_document_est_valide_d_office(self):
        self.client.force_authenticate(self.employe_oseor)
        reponse = self.client.post("/api/documents/", {
            "type_document": TypeDocument.FICHE_BESOIN,
        }, format="json")
        self.assertEqual(reponse.data["statut"], Document.Statut.VALIDE)


class ChaineDeVisasTests(BaseDocuments, APITestCase):
    def setUp(self):
        self.creer_donnees()
        self.document = self.creer_document()

    def viser(self, utilisateur, decision="VALIDE", commentaire=""):
        self.client.force_authenticate(utilisateur)
        return self.client.post(
            f"/api/documents/{self.document.pk}/viser/",
            {"decision": decision, "commentaire": commentaire}, format="json",
        )

    def test_le_role_attendu_peut_viser(self):
        self.assertEqual(self.viser(self.comptable).status_code, 200)

    def test_un_autre_role_est_refuse(self):
        self.assertEqual(self.viser(self.employe).status_code, 403)

    def test_direction_peut_toujours_viser(self):
        """Le DG et l'administrateur visent n'importe quelle étape."""
        self.assertEqual(self.viser(self.admin).status_code, 200)

    def test_le_bon_role_d_une_autre_filiale_ne_voit_pas_le_document(self):
        """
        Le contrôle de `viser` porte sur le rôle SEUL — un comptable d'OSEOR
        le passerait. C'est le périmètre de `get_queryset()` qui l'arrête
        avant, d'où un 404 (document invisible) et non un 403.

        L'étanchéité entre filiales repose donc entièrement sur le queryset :
        toute vue qui exposerait un document hors de ce périmètre rouvrirait
        la brèche. À préserver lors de toute refonte des permissions.
        """
        self.assertEqual(self.viser(self.comptable_oseor).status_code, 404)

    def test_avancement_puis_validation_finale(self):
        self.viser(self.comptable)
        self.document.refresh_from_db()
        self.assertEqual(self.document.etape_visa_courante, 2)
        self.assertEqual(self.document.statut, Document.Statut.EN_COURS)

        self.viser(self.directeur)
        self.document.refresh_from_db()
        self.assertEqual(self.document.statut, Document.Statut.VALIDE)

    def test_refus_cloture_et_conserve_le_motif(self):
        self.viser(self.comptable, decision="REFUSE", commentaire="Hors budget")
        self.document.refresh_from_db()
        self.assertEqual(self.document.statut, Document.Statut.REFUSE)
        self.assertEqual(self.document.motif_rejet, "Hors budget")

    def test_document_deja_traite_refuse_un_nouveau_visa(self):
        self.viser(self.comptable, decision="REFUSE")
        self.assertEqual(self.viser(self.directeur).status_code, 400)

    def test_historique_conserve_chaque_decision(self):
        self.viser(self.comptable, commentaire="OK pour moi")
        self.document.refresh_from_db()
        derniere = self.document.historique_visas[-1]
        self.assertEqual(derniere["utilisateur_id"], self.comptable.pk)
        self.assertEqual(derniere["decision"], "VALIDE")
        self.assertEqual(derniere["commentaire"], "OK pour moi")


class PeutViserTests(BaseDocuments, APITestCase):
    """Champ `peut_viser` : pilote l'affichage du bouton côté frontend."""

    def setUp(self):
        self.creer_donnees()
        self.document = self.creer_document()

    def _peut_viser(self, utilisateur):
        self.client.force_authenticate(utilisateur)
        return self.client.get(
            f"/api/documents/{self.document.pk}/").data["peut_viser"]

    def test_vrai_pour_le_role_attendu(self):
        self.assertTrue(self._peut_viser(self.comptable))

    def test_vrai_pour_la_direction(self):
        self.assertTrue(self._peut_viser(self.directeur))
        self.assertTrue(self._peut_viser(self.admin))

    def test_faux_pour_les_autres(self):
        self.assertFalse(self._peut_viser(self.employe))

    def test_faux_sur_un_document_cloture(self):
        self.document.statut = Document.Statut.VALIDE
        self.document.save()
        self.assertFalse(self._peut_viser(self.comptable))


class ConfigurationEndpointTests(BaseDocuments, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_renvoie_la_config_de_la_filiale(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.get(
            f"/api/documents/configuration/?type_document={TypeDocument.FICHE_BESOIN}")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.data["visas"]), 3)

    def test_type_document_obligatoire(self):
        self.client.force_authenticate(self.employe)
        self.assertEqual(
            self.client.get("/api/documents/configuration/").status_code, 400)

    def test_compte_sans_filiale_refuse(self):
        orphelin = User.objects.create_user(
            "orphelin", password="x", role=User.Role.EMPLOYE)
        self.client.force_authenticate(orphelin)
        reponse = self.client.get(
            f"/api/documents/configuration/?type_document={TypeDocument.FICHE_BESOIN}")
        self.assertEqual(reponse.status_code, 400)
