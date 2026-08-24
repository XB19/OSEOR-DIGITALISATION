"""
Permissions exceptionnelles — article 45 de la Convention Collective
Interprofessionnelle du Togo (révision du 12 décembre 2011).

Deux règles de l'article structurent tout le module et sont testées ici en
premier :

- les permissions sont « non déductibles du congé annuel » : elles ne
  touchent jamais le solde ;
- la condition de six mois d'ancienneté vaut pour les permissions
  syndicales, mais les évènements familiaux en sont expressément
  dispensés.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APITestCase

from applications.conges import services, workflow
from applications.conges.convention import (
    BAREME, DELAI_JUSTIFICATIF_JOURS, MotifPermission, exige_anciennete,
    jours_accordes,
)
from applications.conges.models import DemandeConge, TypeConge
from applications.conges.workflow import DemandeRefusee
from applications.filiales.models import Filiale, Service

User = get_user_model()


class BaremeTests(TestCase):
    """Le barème doit refléter l'article 45 au jour près."""

    def test_jours_par_evenement(self):
        attendu = {
            MotifPermission.DECES_CONJOINT_ASCENDANT_DESCENDANT: 4,
            MotifPermission.DECES_FRERE_SOEUR: 2,
            MotifPermission.DECES_BEAU_PARENT: 3,
            MotifPermission.MARIAGE_TRAVAILLEUR: 3,
            MotifPermission.MARIAGE_PROCHE: 1,
            MotifPermission.NAISSANCE: 2,
            MotifPermission.BAPTEME: 1,
            MotifPermission.DEMENAGEMENT: 1,
        }
        for motif, jours in attendu.items():
            with self.subTest(motif=motif):
                self.assertEqual(jours_accordes(motif), jours)

    def test_evenements_familiaux_dispenses_d_anciennete(self):
        """« même si le travailleur ne justifie pas de six mois d'ancienneté »."""
        for motif in (MotifPermission.DECES_FRERE_SOEUR,
                      MotifPermission.MARIAGE_TRAVAILLEUR,
                      MotifPermission.NAISSANCE,
                      MotifPermission.DEMENAGEMENT):
            with self.subTest(motif=motif):
                self.assertFalse(exige_anciennete(motif))

    def test_permissions_syndicales_soumises_a_anciennete(self):
        self.assertTrue(exige_anciennete(MotifPermission.CONGRES_SYNDICAL))

    def test_congres_syndical_plafonne_a_dix_jours_par_an(self):
        self.assertEqual(
            BAREME[MotifPermission.CONGRES_SYNDICAL]["plafond_annuel"], 10)

    def test_chaque_motif_indique_son_justificatif(self):
        """L'article impose une pièce sous huit jours : elle doit être nommée."""
        for motif, regle in BAREME.items():
            with self.subTest(motif=motif):
                self.assertTrue(regle["justificatif"])

    def test_motif_inconnu(self):
        self.assertEqual(jours_accordes("INVENTE"), 0)


class BasePermissions:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.compta = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.kapi)

        self.directeur = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.rh = User.objects.create_user(
            "rh", password="x", role=User.Role.RH, filiale=self.kapi)
        self.chef = User.objects.create_user(
            "chef", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.compta,
            responsable_hierarchique=self.directeur)
        self.compta.chef = self.chef
        self.compta.save()

        # Ancien : plus de six mois d'ancienneté.
        self.ancien = User.objects.create_user(
            "ancien", password="x", role=User.Role.EMPLOYE, filiale=self.kapi,
            service=self.compta, responsable_hierarchique=self.chef,
            date_embauche=date(2025, 1, 6))

        # Nouveau : embauché la veille du dépôt.
        self.nouveau = User.objects.create_user(
            "nouveau", password="x", role=User.Role.EMPLOYE, filiale=self.kapi,
            service=self.compta, responsable_hierarchique=self.chef,
            date_embauche=date(2027, 7, 1))


class DepotPermissionTests(BasePermissions, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_deces_frere_deux_jours(self):
        demande = workflow.deposer(
            self.ancien, TypeConge.PERMISSION,
            date(2027, 7, 5), date(2027, 7, 6),
            motif_permission=MotifPermission.DECES_FRERE_SOEUR,
            date_evenement=date(2027, 7, 4))

        self.assertEqual(demande.jours_ouvres, 2)
        self.assertEqual(demande.type_conge, TypeConge.PERMISSION)

    def test_depassement_du_bareme_refuse(self):
        """Un décès de frère ouvre 2 jours : en demander 5 est refusé."""
        with self.assertRaises(DemandeRefusee) as erreur:
            workflow.deposer(
                self.ancien, TypeConge.PERMISSION,
                date(2027, 7, 5), date(2027, 7, 9),
                motif_permission=MotifPermission.DECES_FRERE_SOEUR)

        self.assertIn("2 jour(s)", str(erreur.exception))

    def test_evenement_familial_sans_anciennete_accepte(self):
        """L'article 45 dispense expressément les évènements familiaux."""
        demande = workflow.deposer(
            self.nouveau, TypeConge.PERMISSION,
            date(2027, 7, 5), date(2027, 7, 7),
            motif_permission=MotifPermission.MARIAGE_TRAVAILLEUR)

        self.assertEqual(demande.jours_ouvres, 3)

    def test_permission_syndicale_sans_anciennete_refusee(self):
        with self.assertRaises(DemandeRefusee) as erreur:
            workflow.deposer(
                self.nouveau, TypeConge.PERMISSION,
                date(2027, 7, 5), date(2027, 7, 9),
                motif_permission=MotifPermission.CONGRES_SYNDICAL)

        self.assertIn("ancienneté", str(erreur.exception))

    def test_permission_syndicale_avec_anciennete_acceptee(self):
        demande = workflow.deposer(
            self.ancien, TypeConge.PERMISSION,
            date(2027, 7, 5), date(2027, 7, 9),
            motif_permission=MotifPermission.CONGRES_SYNDICAL)

        self.assertEqual(demande.jours_ouvres, 5)

    def test_motif_obligatoire(self):
        with self.assertRaises(DemandeRefusee):
            workflow.deposer(
                self.ancien, TypeConge.PERMISSION,
                date(2027, 7, 5), date(2027, 7, 6))

    def test_motif_inconnu_refuse(self):
        with self.assertRaises(DemandeRefusee):
            workflow.deposer(
                self.ancien, TypeConge.PERMISSION,
                date(2027, 7, 5), date(2027, 7, 6),
                motif_permission="VACANCES_A_LA_PLAGE")

    def test_motif_de_permission_sur_un_conge_annuel_refuse(self):
        with self.assertRaises(DemandeRefusee):
            workflow.deposer(
                self.ancien, TypeConge.ANNUEL,
                date(2027, 7, 5), date(2027, 7, 6),
                motif_permission=MotifPermission.BAPTEME)


class NonDeductibiliteTests(BasePermissions, TestCase):
    """
    « Non déductibles du congé annuel » : c'est la règle qui distingue une
    permission d'un congé, et celle qu'un salarié contestera en premier si
    elle est mal appliquée.
    """

    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.ancien, date(2027, 7, 1))

    def test_solde_intact_apres_depot(self):
        avant = services.solde(self.ancien)

        workflow.deposer(
            self.ancien, TypeConge.PERMISSION,
            date(2027, 7, 5), date(2027, 7, 6),
            motif_permission=MotifPermission.DECES_FRERE_SOEUR)

        self.assertEqual(services.solde_disponible(self.ancien), avant)

    def test_solde_intact_apres_validation(self):
        demande = workflow.deposer(
            self.ancien, TypeConge.PERMISSION,
            date(2027, 7, 5), date(2027, 7, 6),
            motif_permission=MotifPermission.DECES_FRERE_SOEUR)
        avant = services.solde(self.ancien)

        workflow.decider(demande, self.chef, approuvee=True)

        self.assertEqual(services.solde(self.ancien), avant)

    def test_aucun_solde_requis(self):
        """Un salarié à zéro congé garde droit à ses permissions."""
        demande = workflow.deposer(
            self.nouveau, TypeConge.PERMISSION,
            date(2027, 7, 5), date(2027, 7, 6),
            motif_permission=MotifPermission.NAISSANCE)

        self.assertEqual(services.solde(self.nouveau), Decimal("0"))
        self.assertEqual(demande.jours_ouvres, 2)


class JustificatifTests(BasePermissions, TestCase):
    def setUp(self):
        self.creer_donnees()

    def _permission(self, date_evenement=None):
        return workflow.deposer(
            self.ancien, TypeConge.PERMISSION,
            date(2027, 7, 5), date(2027, 7, 6),
            motif_permission=MotifPermission.DECES_FRERE_SOEUR,
            date_evenement=date_evenement)

    def test_piece_attendue_nommee(self):
        self.assertEqual(self._permission().justificatif_attendu, "Acte de décès")

    def test_delai_de_huit_jours_apres_l_evenement(self):
        demande = self._permission(date_evenement=date(2027, 7, 4))

        self.assertEqual(
            demande.date_limite_justificatif,
            date(2027, 7, 4) + timedelta(days=DELAI_JUSTIFICATIF_JOURS),
        )

    def test_delai_court_depuis_le_debut_sans_date_d_evenement(self):
        demande = self._permission()
        self.assertEqual(
            demande.date_limite_justificatif,
            date(2027, 7, 5) + timedelta(days=DELAI_JUSTIFICATIF_JOURS),
        )

    def test_retard_signale(self):
        """Signalement pour les RH : l'article fixe un délai, pas une déchéance."""
        demande = self._permission(date_evenement=date(2020, 1, 1))
        self.assertTrue(demande.justificatif_en_retard)

    def test_pas_de_retard_sur_un_conge_annuel(self):
        demande = DemandeConge(
            utilisateur=self.ancien, type_conge=TypeConge.ANNUEL,
            date_debut=date(2020, 1, 1), date_fin=date(2020, 1, 2))
        self.assertFalse(demande.justificatif_en_retard)


class ValidationModeleTests(BasePermissions, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_permission_sans_motif_refusee(self):
        demande = DemandeConge(
            utilisateur=self.ancien, type_conge=TypeConge.PERMISSION,
            date_debut=date(2027, 7, 5), date_fin=date(2027, 7, 6))
        with self.assertRaises(ValidationError):
            demande.full_clean()

    def test_motif_sur_conge_annuel_refuse(self):
        demande = DemandeConge(
            utilisateur=self.ancien, type_conge=TypeConge.ANNUEL,
            date_debut=date(2027, 7, 5), date_fin=date(2027, 7, 6),
            motif_permission=MotifPermission.BAPTEME)
        with self.assertRaises(ValidationError):
            demande.full_clean()


class PermissionAPITests(BasePermissions, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_bareme_expose(self):
        """Le frontend doit pouvoir construire sa liste déroulante."""
        self.client.force_authenticate(self.ancien)

        reponse = self.client.get("/api/conges/bareme_permissions/")

        self.assertEqual(reponse.status_code, 200)
        codes = [m["code"] for m in reponse.data]
        self.assertIn(MotifPermission.NAISSANCE, codes)

        naissance = next(
            m for m in reponse.data if m["code"] == MotifPermission.NAISSANCE)
        self.assertEqual(naissance["jours"], 2)
        self.assertFalse(naissance["anciennete_requise"])

    def test_depot_par_l_api(self):
        self.client.force_authenticate(self.ancien)

        reponse = self.client.post("/api/conges/", {
            "type_conge": TypeConge.PERMISSION,
            "date_debut": "2027-07-05",
            "date_fin": "2027-07-06",
            "motif_permission": MotifPermission.DECES_FRERE_SOEUR,
            "date_evenement": "2027-07-04",
        }, format="json")

        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse.data["jours_ouvres"], 2)
        self.assertEqual(reponse.data["justificatif_attendu"], "Acte de décès")

    def test_depassement_renvoie_400_explicite(self):
        self.client.force_authenticate(self.ancien)

        reponse = self.client.post("/api/conges/", {
            "type_conge": TypeConge.PERMISSION,
            "date_debut": "2027-07-05",
            "date_fin": "2027-07-09",
            "motif_permission": MotifPermission.BAPTEME,
        }, format="json")

        self.assertEqual(reponse.status_code, 400)
        self.assertIn("1 jour(s)", reponse.data["detail"])
