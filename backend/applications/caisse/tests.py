"""
Caisse et bons de sortie.

Le module manipule des espèces : chaque règle testée ici correspond à un
contrôle qu'un auditeur viendrait vérifier — preuve à l'entrée, niveau
d'autorisation, solde jamais négatif, monnaie rendue.
"""

from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from applications.caisse import services
from applications.caisse.circuits import destinataire_acceptable
from applications.caisse.models import BonSortie, Caisse, MouvementCaisse
from applications.caisse.services import OperationRefusee
from applications.filiales.models import Filiale, Service

User = get_user_model()


def piece(nom="cheque.pdf"):
    return SimpleUploadedFile(nom, b"preuve de transaction",
                              content_type="application/pdf")


class BaseCaisse:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")
        self.service = Service.objects.create(
            nom="Moyens Généraux", code="MG", filiale=self.kapi)

        self.dg = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.caissier = User.objects.create_user(
            "caissier", password="x", role=User.Role.COMPTABLE, filiale=self.kapi)
        self.chef = User.objects.create_user(
            "chef", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.service)
        self.salarie = User.objects.create_user(
            "salarie", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.service)
        self.etranger = User.objects.create_user(
            "etranger", password="x", role=User.Role.COMPTABLE,
            filiale=self.oseor)

        self.caisse = Caisse.objects.create(
            nom="Caisse principale", code="PRINC", filiale=self.kapi,
            detenteur=self.caissier)

    def approvisionner(self, montant="500000"):
        return services.alimenter(
            self.caisse, montant, self.caissier, reference="CHQ-001")


class SoldeTests(BaseCaisse, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_solde_vide_au_depart(self):
        self.assertEqual(self.caisse.solde, Decimal("0"))

    def test_solde_est_la_somme_du_registre(self):
        """Jamais un compteur : la somme des écritures, toujours."""
        self.approvisionner("300000")
        services.corriger(self.caisse, "-5000", self.dg, "écart constaté")

        self.assertEqual(self.caisse.solde, Decimal("295000"))

    def test_meme_code_dans_deux_filiales(self):
        Caisse.objects.create(
            nom="Caisse OSEOR", code="PRINC", filiale=self.oseor)
        self.assertEqual(
            Caisse.objects.filter(code="PRINC").count(), 2)


class AlimentationTests(BaseCaisse, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_preuve_obligatoire(self):
        """On n'augmente pas une caisse sur parole."""
        with self.assertRaises(OperationRefusee) as erreur:
            services.alimenter(self.caisse, "100000", self.caissier)
        self.assertIn("preuve", str(erreur.exception).lower())

    def test_reference_suffit(self):
        mouvement = services.alimenter(
            self.caisse, "100000", self.caissier, reference="VIR-2027-45")
        self.assertEqual(mouvement.montant, Decimal("100000"))

    def test_justificatif_suffit(self):
        mouvement = services.alimenter(
            self.caisse, "100000", self.caissier, justificatif=piece())
        self.assertTrue(mouvement.justificatif)

    def test_montant_negatif_refuse(self):
        with self.assertRaises(OperationRefusee):
            services.alimenter(
                self.caisse, "-1000", self.caissier, reference="X")

    def test_seul_le_detenteur_ou_la_direction(self):
        with self.assertRaises(OperationRefusee):
            services.alimenter(
                self.caisse, "1000", self.salarie, reference="X")

    def test_comptable_d_une_autre_filiale_refuse(self):
        with self.assertRaises(OperationRefusee):
            services.alimenter(
                self.caisse, "1000", self.etranger, reference="X")

    def test_modele_refuse_une_alimentation_sans_preuve(self):
        """Garde-fou au niveau du modèle, pas seulement du service."""
        mouvement = MouvementCaisse(
            caisse=self.caisse,
            type_mouvement=MouvementCaisse.TypeMouvement.ALIMENTATION,
            montant=Decimal("1000"), cree_par=self.caissier,
            date_operation="2027-01-05")
        with self.assertRaises(ValidationError):
            mouvement.full_clean()

    def test_sens_du_montant_controle(self):
        mouvement = MouvementCaisse(
            caisse=self.caisse,
            type_mouvement=MouvementCaisse.TypeMouvement.SORTIE,
            montant=Decimal("1000"), cree_par=self.caissier,
            date_operation="2027-01-05")
        with self.assertRaises(ValidationError):
            mouvement.full_clean()


class TransportTests(BaseCaisse, TestCase):
    """Une course ne s'arbitre pas avant d'être payée."""

    def setUp(self):
        self.creer_donnees()
        self.approvisionner()

    def test_taxi_autorise_d_office(self):
        bon = services.deposer(
            self.caisse, self.salarie, "Course client", "3000",
            BonSortie.TypeDepense.TRANSPORT,
            moyen_transport=BonSortie.MoyenTransport.TAXI)

        self.assertEqual(bon.statut, BonSortie.Statut.AUTORISE)
        self.assertIsNone(bon.destinataire)

    def test_moto_autorise_d_office(self):
        bon = services.deposer(
            self.caisse, self.salarie, "Course", "1500",
            BonSortie.TypeDepense.TRANSPORT,
            moyen_transport=BonSortie.MoyenTransport.MOTO)
        self.assertEqual(bon.statut, BonSortie.Statut.AUTORISE)

    def test_gozem_exige_un_justificatif(self):
        """L'application conserve l'historique : la pièce est produisible."""
        with self.assertRaises(OperationRefusee) as erreur:
            services.deposer(
                self.caisse, self.salarie, "Course", "4000",
                BonSortie.TypeDepense.TRANSPORT,
                moyen_transport=BonSortie.MoyenTransport.GOZEM)

        self.assertIn("justificatif", str(erreur.exception).lower())

    def test_gozem_avec_justificatif_passe(self):
        bon = services.deposer(
            self.caisse, self.salarie, "Course", "4000",
            BonSortie.TypeDepense.TRANSPORT,
            moyen_transport=BonSortie.MoyenTransport.GOZEM,
            justificatif=piece("gozem.png"))

        self.assertEqual(bon.statut, BonSortie.Statut.AUTORISE)
        self.assertTrue(bon.exige_justificatif)

    def test_moyen_obligatoire(self):
        with self.assertRaises(OperationRefusee):
            services.deposer(
                self.caisse, self.salarie, "Course", "3000",
                BonSortie.TypeDepense.TRANSPORT)

    def test_transport_ne_se_decide_pas(self):
        bon = services.deposer(
            self.caisse, self.salarie, "Course", "3000",
            BonSortie.TypeDepense.TRANSPORT,
            moyen_transport=BonSortie.MoyenTransport.TAXI)

        with self.assertRaises(OperationRefusee):
            services.decider(bon, self.chef, autorise=True)


@override_settings(CAISSE_SEUIL_DIRECTION="100000")
class AdressageTests(BaseCaisse, TestCase):
    """Le niveau d'autorisation se déduit du montant, pas du demandeur."""

    def setUp(self):
        self.creer_donnees()
        self.approvisionner()

    def test_chef_suffit_sous_le_seuil(self):
        self.assertTrue(destinataire_acceptable(self.chef, Decimal("50000")))

    def test_chef_insuffisant_au_dessus(self):
        self.assertFalse(destinataire_acceptable(self.chef, Decimal("200000")))

    def test_direction_toujours_acceptable(self):
        self.assertTrue(destinataire_acceptable(self.dg, Decimal("999999")))

    def test_depot_refuse_si_le_niveau_est_insuffisant(self):
        with self.assertRaises(OperationRefusee) as erreur:
            services.deposer(
                self.caisse, self.salarie, "Achat matériel", "200000",
                BonSortie.TypeDepense.AUTRE, destinataire=self.chef)

        self.assertIn("autorisation", str(erreur.exception).lower())

    def test_destinataire_obligatoire_hors_transport(self):
        with self.assertRaises(OperationRefusee):
            services.deposer(
                self.caisse, self.salarie, "Achat", "10000",
                BonSortie.TypeDepense.AUTRE)

    def test_on_ne_s_adresse_pas_le_bon_a_soi_meme(self):
        with self.assertRaises(OperationRefusee):
            services.deposer(
                self.caisse, self.chef, "Achat", "10000",
                BonSortie.TypeDepense.AUTRE, destinataire=self.chef)

    def test_moyen_de_transport_sur_autre_depense_refuse(self):
        with self.assertRaises(OperationRefusee):
            services.deposer(
                self.caisse, self.salarie, "Achat", "10000",
                BonSortie.TypeDepense.AUTRE,
                moyen_transport=BonSortie.MoyenTransport.TAXI,
                destinataire=self.chef)


class AutorisationTests(BaseCaisse, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.approvisionner()
        self.bon = services.deposer(
            self.caisse, self.salarie, "Fournitures", "50000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)

    def test_le_destinataire_autorise(self):
        services.decider(self.bon, self.chef, autorise=True)
        self.bon.refresh_from_db()
        self.assertEqual(self.bon.statut, BonSortie.Statut.AUTORISE)

    def test_un_tiers_ne_peut_pas(self):
        with self.assertRaises(OperationRefusee):
            services.decider(self.bon, self.caissier, autorise=True)

    def test_la_direction_peut_trancher_directement(self):
        services.decider(self.bon, self.dg, autorise=True)
        self.bon.refresh_from_db()
        self.assertEqual(self.bon.statut, BonSortie.Statut.AUTORISE)

    def test_refus(self):
        services.decider(self.bon, self.chef, autorise=False, motif="hors budget")
        self.bon.refresh_from_db()
        self.assertEqual(self.bon.statut, BonSortie.Statut.REFUSE)

    def test_deja_traite(self):
        services.decider(self.bon, self.chef, autorise=True)
        with self.assertRaises(OperationRefusee):
            services.decider(self.bon, self.dg, autorise=False)


class PaiementTests(BaseCaisse, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.approvisionner("100000")
        self.bon = services.deposer(
            self.caisse, self.salarie, "Fournitures", "40000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)
        services.decider(self.bon, self.chef, autorise=True)
        self.bon.refresh_from_db()

    def test_paiement_debite_la_caisse(self):
        services.payer(self.bon, self.caissier)

        self.caisse.refresh_from_db()
        self.assertEqual(self.caisse.solde, Decimal("60000"))
        self.bon.refresh_from_db()
        self.assertEqual(self.bon.statut, BonSortie.Statut.PAYE)

    def test_non_autorise_non_payable(self):
        autre = services.deposer(
            self.caisse, self.salarie, "Autre", "1000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)
        with self.assertRaises(OperationRefusee):
            services.payer(autre, self.caissier)

    def test_solde_insuffisant(self):
        gros = services.deposer(
            self.caisse, self.salarie, "Gros achat", "90000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)
        services.decider(gros, self.chef, autorise=True)
        gros.refresh_from_db()

        services.payer(self.bon, self.caissier)  # il reste 60 000

        with self.assertRaises(OperationRefusee) as erreur:
            services.payer(gros, self.caissier)
        self.assertIn("insuffisant", str(erreur.exception).lower())

    def test_seul_le_detenteur_decaisse(self):
        with self.assertRaises(OperationRefusee):
            services.payer(self.bon, self.salarie)


class RetourTests(BaseCaisse, TestCase):
    """Retour en caisse : la monnaie non dépensée revient."""

    def setUp(self):
        self.creer_donnees()
        self.approvisionner("100000")
        self.bon = services.deposer(
            self.caisse, self.salarie, "Achat", "10000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)
        services.decider(self.bon, self.chef, autorise=True)
        self.bon.refresh_from_db()
        services.payer(self.bon, self.caissier)
        self.bon.refresh_from_db()

    def test_la_monnaie_revient_en_caisse(self):
        services.rendre_monnaie(self.bon, "3000", self.salarie)

        self.caisse.refresh_from_db()
        self.assertEqual(self.caisse.solde, Decimal("93000"))

    def test_montants_du_bon(self):
        services.rendre_monnaie(self.bon, "3000", self.salarie)
        self.bon.refresh_from_db()

        self.assertEqual(self.bon.montant_paye, Decimal("10000"))
        self.assertEqual(self.bon.montant_rendu, Decimal("3000"))
        self.assertEqual(self.bon.montant_consomme, Decimal("7000"))

    def test_on_ne_rend_pas_plus_que_sorti(self):
        with self.assertRaises(OperationRefusee):
            services.rendre_monnaie(self.bon, "15000", self.salarie)

    def test_retours_cumules_plafonnes(self):
        services.rendre_monnaie(self.bon, "6000", self.salarie)
        with self.assertRaises(OperationRefusee):
            services.rendre_monnaie(self.bon, "6000", self.salarie)

    def test_bon_non_paye(self):
        autre = services.deposer(
            self.caisse, self.salarie, "Autre", "1000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)
        with self.assertRaises(OperationRefusee):
            services.rendre_monnaie(autre, "500", self.salarie)


class CaisseAPITests(BaseCaisse, APITestCase):
    def setUp(self):
        self.creer_donnees()
        self.approvisionner("200000")

    def test_registre_visible(self):
        self.client.force_authenticate(self.caissier)
        reponse = self.client.get(f"/api/caisses/{self.caisse.pk}/registre/")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.data), 1)

    def test_solde_expose(self):
        self.client.force_authenticate(self.caissier)
        reponse = self.client.get(f"/api/caisses/{self.caisse.pk}/")
        self.assertEqual(Decimal(reponse.data["solde"]), Decimal("200000"))

    def test_alimentation_sans_preuve_refusee(self):
        self.client.force_authenticate(self.caissier)
        reponse = self.client.post(
            f"/api/caisses/{self.caisse.pk}/alimenter/",
            {"montant": "50000"}, format="multipart")
        self.assertEqual(reponse.status_code, 400)

    def test_depot_transport_par_l_api(self):
        self.client.force_authenticate(self.salarie)
        reponse = self.client.post("/api/bons-sortie/", {
            "caisse": self.caisse.pk, "objet": "Course client",
            "montant": "3000", "type_depense": "TRANSPORT",
            "moyen_transport": "TAXI",
        }, format="multipart")

        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse.data["statut"], BonSortie.Statut.AUTORISE)

    def test_regles_exposees(self):
        self.client.force_authenticate(self.salarie)
        reponse = self.client.get("/api/bons-sortie/regles/")

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("GOZEM", reponse.data["moyens_avec_justificatif"])

    def test_a_autoriser(self):
        bon = services.deposer(
            self.caisse, self.salarie, "Achat", "20000",
            BonSortie.TypeDepense.AUTRE, destinataire=self.chef)

        self.client.force_authenticate(self.chef)
        reponse = self.client.get("/api/bons-sortie/a_autoriser/")

        self.assertEqual(len(reponse.data), 1)
        self.assertEqual(reponse.data[0]["reference"], bon.reference)

    def test_anonyme_refuse(self):
        self.assertIn(
            self.client.get("/api/caisses/").status_code, (401, 403))
