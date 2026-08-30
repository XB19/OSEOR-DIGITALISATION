"""
Pièce imprimable d'un bon de sortie.

Le bon de caisse détient la vérité — montant, autorisation, mouvement
d'argent. Le `Document` engendré au décaissement n'est que sa forme
papier. Il ne doit exister qu'un seul chemin pour créer un bon de sortie,
sinon deux bons concurrents cohabitent et l'un d'eux ne touche aucune
caisse.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from applications.caisse import services
from applications.caisse.models import BonSortie, Caisse
from applications.documents.models import (
    ConfigurationDocument, Document, TypeDocument,
)
from applications.filiales.models import Filiale, Service

User = get_user_model()


class BasePiece:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.service = Service.objects.create(
            nom="Moyens Généraux", code="MG", filiale=self.kapi)

        self.dg = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.caissier = User.objects.create_user(
            "caissier", password="x", role=User.Role.COMPTABLE,
            filiale=self.kapi)
        self.chef = User.objects.create_user(
            "chef", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.service)
        self.salarie = User.objects.create_user(
            "salarie", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.service)

        self.caisse = Caisse.objects.create(
            nom="Caisse principale", code="PRINC", filiale=self.kapi,
            detenteur=self.caissier)
        services.alimenter(
            self.caisse, "200000", self.caissier, reference="CHQ-001")

    def bon_paye(self):
        bon = services.deposer(
            self.caisse, self.salarie, "Fournitures de bureau", "45000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)
        services.decider(bon, self.chef, autorise=True)
        bon.refresh_from_db()
        services.payer(bon, self.caissier)
        bon.refresh_from_db()
        return bon


class GenerationTests(BasePiece, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_aucune_piece_avant_paiement(self):
        """La pièce naît au décaissement, pas à la demande."""
        bon = services.deposer(
            self.caisse, self.salarie, "Achat", "10000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)
        self.assertIsNone(bon.document_id)

    def test_piece_engendree_au_paiement(self):
        bon = self.bon_paye()

        self.assertIsNotNone(bon.document_id)
        self.assertEqual(
            bon.document.type_document, TypeDocument.BON_SORTIE_CAISSE)

    def test_la_piece_reprend_la_reference_du_bon(self):
        """Un seul numéro pour les deux : ils désignent la même dépense."""
        bon = self.bon_paye()
        self.assertEqual(bon.document.numero, bon.reference)

    def test_montant_et_filiale_repris(self):
        bon = self.bon_paye()

        self.assertEqual(bon.document.montant_total, Decimal("45000"))
        self.assertEqual(bon.document.filiale, self.kapi)
        self.assertEqual(bon.document.demandeur, self.salarie)

    def test_la_piece_montre_qui_a_autorise(self):
        """
        L'historique de visas reprend les décisions réellement prises,
        pas une chaîne théorique : c'est ce que le PDF imprime.
        """
        bon = self.bon_paye()

        visas = bon.document.historique_visas
        self.assertEqual(len(visas), 1)
        self.assertEqual(visas[0]["utilisateur_id"], self.chef.pk)
        self.assertEqual(visas[0]["decision"], "VALIDE")

    def test_entete_renseignee(self):
        bon = self.bon_paye()
        entete = bon.document.champs_entete

        self.assertEqual(entete["beneficiaire"], self.salarie.nom_complet)
        self.assertEqual(entete["autorise_par"], self.chef.nom_complet)
        self.assertEqual(entete["caisse"], self.caisse.nom)

    def test_transport_engendre_aussi_une_piece(self):
        bon = services.deposer(
            self.caisse, self.salarie, "Course client", "3000",
            BonSortie.TypeDepense.TRANSPORT,
            moyen_transport=BonSortie.MoyenTransport.TAXI)
        services.payer(bon, self.caissier)
        bon.refresh_from_db()

        self.assertIsNotNone(bon.document_id)
        self.assertEqual(
            bon.document.champs_entete["moyen_transport"], "Taxi")

    def test_idempotente(self):
        """Un bon n'a qu'une pièce, même si la génération est rejouée."""
        bon = self.bon_paye()
        premier = bon.document_id

        services.engendrer_piece(bon)

        bon.refresh_from_db()
        self.assertEqual(bon.document_id, premier)
        self.assertEqual(
            Document.objects.filter(numero=bon.reference).count(), 1)


class CheminUniqueTests(BasePiece, APITestCase):
    """Un bon de sortie ne se crée que depuis la caisse."""

    def setUp(self):
        self.creer_donnees()
        ConfigurationDocument.objects.create(
            filiale=self.kapi,
            type_document=TypeDocument.BON_SORTIE_CAISSE,
            colonnes=[], visas=[{"cle": "demandeur", "libelle": "Demandeur"}])

    def test_creation_directe_refusee(self):
        self.client.force_authenticate(self.salarie)

        reponse = self.client.post("/api/documents/", {
            "type_document": TypeDocument.BON_SORTIE_CAISSE,
            "lignes": [{"objet": "contournement", "montant_debit": "50000"}],
            "montant_total": "50000",
        }, format="json")

        self.assertEqual(reponse.status_code, 400)

    def test_le_message_indique_le_bon_chemin(self):
        self.client.force_authenticate(self.salarie)

        reponse = self.client.post("/api/documents/", {
            "type_document": TypeDocument.BON_SORTIE_CAISSE,
        }, format="json")

        self.assertIn("/api/bons-sortie/", str(reponse.data))

    def test_les_autres_types_restent_creables(self):
        """La restriction ne vise que le bon de sortie."""
        ConfigurationDocument.objects.create(
            filiale=self.kapi,
            type_document=TypeDocument.FICHE_BESOIN,
            colonnes=[], visas=[{"cle": "demandeur", "libelle": "Demandeur"}])

        self.client.force_authenticate(self.salarie)
        reponse = self.client.post("/api/documents/", {
            "type_document": TypeDocument.FICHE_BESOIN,
            "lignes": [{"motif": "Ramettes"}],
        }, format="json")

        self.assertEqual(reponse.status_code, 201)


class PdfTests(BasePiece, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_pdf_indisponible_avant_paiement(self):
        bon = services.deposer(
            self.caisse, self.salarie, "Achat", "10000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)

        self.client.force_authenticate(self.salarie)
        reponse = self.client.get(f"/api/bons-sortie/{bon.pk}/pdf/")

        self.assertEqual(reponse.status_code, 400)

    def test_pdf_apres_paiement(self):
        """Le générateur du moteur documentaire s'applique tel quel."""
        bon = self.bon_paye()

        self.client.force_authenticate(self.salarie)
        reponse = self.client.get(f"/api/bons-sortie/{bon.pk}/pdf/")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["Content-Type"], "application/pdf")
        self.assertTrue(reponse.content.startswith(b"%PDF"))
