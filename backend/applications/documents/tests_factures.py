"""
Factures : circuit de visa et suivi de règlement.

Le point à ne pas confondre : `statut` (le circuit de visas) et
`statut_paiement` (le règlement) sont deux choses distinctes. Une facture
peut être entièrement visée et rester impayée — les confondre ferait
disparaître les impayés du suivi.
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from applications.documents.models import (
    ConfigurationDocument, Document, TypeDocument,
)
from applications.filiales.models import Filiale

User = get_user_model()


class BaseFactures:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")

        ConfigurationDocument.objects.create(
            filiale=self.kapi,
            type_document=TypeDocument.FACTURE,
            colonnes=[
                {"cle": "designation", "libelle": "Désignation"},
                {"cle": "montant", "libelle": "Montant"},
            ],
            visas=[
                {"cle": "saisie_par", "libelle": "Saisie par"},
                {"cle": "comptable", "libelle": "Vérification comptable",
                 "role": "COMPTABLE"},
                {"cle": "dg", "libelle": "Approbation du DG", "role": "DIRECTEUR"},
            ],
        )

        self.secretaire = User.objects.create_user(
            "secretaire", password="x", role=User.Role.SECRETAIRE, filiale=self.kapi)
        self.comptable = User.objects.create_user(
            "comptable", password="x", role=User.Role.COMPTABLE, filiale=self.kapi)
        self.comptable_oseor = User.objects.create_user(
            "comptable2", password="x", role=User.Role.COMPTABLE, filiale=self.oseor)
        self.directeur = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.employe = User.objects.create_user(
            "employe", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)

    def creer_facture(self, statut=Document.Statut.VALIDE, entete=None):
        return Document.objects.create(
            filiale=self.kapi,
            type_document=TypeDocument.FACTURE,
            demandeur=self.secretaire,
            numero=f"KAPI-FAC-2026-{Document.objects.count() + 1:04d}",
            champs_entete=entete if entete is not None else {
                "fournisseur": "Papeterie du Golfe",
                "date_echeance": "2027-12-31",
            },
            lignes=[{"designation": "Ramettes A4", "montant": "150000"}],
            montant_total="150000",
            statut=statut,
            etape_visa_courante=3,
        )


class CircuitFactureTests(BaseFactures, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_creation_numerotee_fac(self):
        self.client.force_authenticate(self.secretaire)

        reponse = self.client.post("/api/documents/", {
            "type_document": TypeDocument.FACTURE,
            "champs_entete": {"fournisseur": "Papeterie du Golfe"},
            "lignes": [{"designation": "Ramettes", "montant": "150000"}],
            "montant_total": "150000",
        }, format="json")

        self.assertEqual(reponse.status_code, 201)
        self.assertTrue(reponse.data["numero"].startswith("KAPI-FAC-"))

    def test_visa_comptable_puis_dg(self):
        facture = self.creer_facture(statut=Document.Statut.EN_COURS)
        Document.objects.filter(pk=facture.pk).update(etape_visa_courante=1)

        self.client.force_authenticate(self.comptable)
        r1 = self.client.post(f"/api/documents/{facture.pk}/viser/",
                              {"decision": "VALIDE"}, format="json")
        self.assertEqual(r1.status_code, 200)

        self.client.force_authenticate(self.directeur)
        r2 = self.client.post(f"/api/documents/{facture.pk}/viser/",
                              {"decision": "VALIDE"}, format="json")
        self.assertEqual(r2.status_code, 200)

        facture.refresh_from_db()
        self.assertEqual(facture.statut, Document.Statut.VALIDE)


class StatutPaiementTests(BaseFactures, APITestCase):
    def setUp(self):
        self.creer_donnees()
        self.facture = self.creer_facture()

    def _regler(self, utilisateur, statut="PAYEE"):
        self.client.force_authenticate(utilisateur)
        return self.client.post(
            f"/api/documents/{self.facture.pk}/statut_paiement/",
            {"statut_paiement": statut}, format="json")

    def test_a_payer_par_defaut(self):
        """Une facture validée n'est pas une facture payée."""
        self.assertEqual(
            self.facture.statut_paiement, Document.StatutPaiement.A_PAYER)

    def test_comptable_constate_le_reglement(self):
        reponse = self._regler(self.comptable)

        self.assertEqual(reponse.status_code, 200)
        self.facture.refresh_from_db()
        self.assertEqual(
            self.facture.statut_paiement, Document.StatutPaiement.PAYEE)

    def test_direction_aussi(self):
        self.assertEqual(self._regler(self.directeur).status_code, 200)

    def test_employe_refuse(self):
        """C'est la trésorerie qui constate un règlement, pas le demandeur."""
        self.assertEqual(self._regler(self.employe).status_code, 403)

    def test_secretaire_demandeuse_refusee(self):
        self.assertEqual(self._regler(self.secretaire).status_code, 403)

    def test_comptable_d_une_autre_filiale_ne_voit_pas_la_facture(self):
        self.assertEqual(self._regler(self.comptable_oseor).status_code, 404)

    def test_statut_invalide_refuse(self):
        reponse = self._regler(self.comptable, statut="REMBOURSEE")
        self.assertEqual(reponse.status_code, 400)

    def test_facture_non_validee_refusee(self):
        en_cours = self.creer_facture(statut=Document.Statut.EN_COURS)
        self.client.force_authenticate(self.comptable)

        reponse = self.client.post(
            f"/api/documents/{en_cours.pk}/statut_paiement/",
            {"statut_paiement": "PAYEE"}, format="json")

        self.assertEqual(reponse.status_code, 400)

    def test_action_reservee_aux_factures(self):
        autre = Document.objects.create(
            filiale=self.kapi, type_document=TypeDocument.FICHE_BESOIN,
            demandeur=self.secretaire, numero="KAPI-FB-2026-0099",
            statut=Document.Statut.VALIDE)

        self.client.force_authenticate(self.comptable)
        reponse = self.client.post(
            f"/api/documents/{autre.pk}/statut_paiement/",
            {"statut_paiement": "PAYEE"}, format="json")

        self.assertEqual(reponse.status_code, 400)

    def test_le_visa_reste_intact(self):
        """Constater un règlement ne doit pas toucher au circuit de visas."""
        avant = self.facture.historique_visas

        self._regler(self.comptable)

        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Document.Statut.VALIDE)
        self.assertEqual(self.facture.historique_visas, avant)

    def test_journalise(self):
        from applications.journalisation.models import JournalAction

        self._regler(self.comptable)

        self.assertTrue(
            JournalAction.objects.filter(action="FACTURE_PAIEMENT").exists())


class EcheanceTests(BaseFactures, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_echeance_depassee(self):
        facture = self.creer_facture(entete={
            "date_echeance": (date.today() - timedelta(days=5)).isoformat()})
        self.assertTrue(facture.echeance_depassee)

    def test_echeance_a_venir(self):
        facture = self.creer_facture(entete={
            "date_echeance": (date.today() + timedelta(days=5)).isoformat()})
        self.assertFalse(facture.echeance_depassee)

    def test_facture_payee_jamais_en_retard(self):
        facture = self.creer_facture(entete={
            "date_echeance": (date.today() - timedelta(days=30)).isoformat(),
            "statut_paiement": "PAYEE",
        })
        self.assertFalse(facture.echeance_depassee)

    def test_sans_echeance(self):
        self.assertFalse(self.creer_facture(entete={}).echeance_depassee)

    def test_echeance_illisible_ne_plante_pas(self):
        """Une saisie libre incorrecte ne doit pas casser l'affichage d'une liste."""
        facture = self.creer_facture(entete={"date_echeance": "bientot"})
        self.assertFalse(facture.echeance_depassee)

    def test_ne_concerne_pas_les_autres_documents(self):
        autre = Document.objects.create(
            filiale=self.kapi, type_document=TypeDocument.FICHE_BESOIN,
            demandeur=self.secretaire, numero="KAPI-FB-2026-0098",
            champs_entete={"date_echeance": "2000-01-01"})
        self.assertFalse(autre.echeance_depassee)
        self.assertEqual(autre.statut_paiement, "")
