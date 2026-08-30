"""
Socle des circuits de validation : désignation des acteurs, validation
directe, observateurs.

Ces règles décident qui peut approuver quoi dans toute l'application. Une
erreur ici laisse passer une signature qui n'aurait pas dû l'être — d'où
une couverture plus serrée que la moyenne.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from applications.filiales.models import Filiale, Service
from applications.validation.circuits import (
    Circuit, Etape, Resolveur, etapes_sautees, peut_agir, resoudre_acteurs,
)
from applications.validation.models import DecisionValidation
from applications.validation.services import (
    ValidationRefusee, enregistrer_decision, notifier_observateurs,
)
from applications.notifications.models import Notification

User = get_user_model()


class BaseCircuit:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")
        self.compta = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.kapi)

        self.dg = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.rh = User.objects.create_user(
            "rh", password="x", role=User.Role.RH, filiale=self.kapi)
        self.chef = User.objects.create_user(
            "chef", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.compta)
        self.compta.chef = self.chef
        self.compta.save()

        self.comptable_kapi = User.objects.create_user(
            "compta_kapi", password="x", role=User.Role.COMPTABLE,
            filiale=self.kapi)
        self.comptable_oseor = User.objects.create_user(
            "compta_oseor", password="x", role=User.Role.COMPTABLE,
            filiale=self.oseor)

        self.salarie = User.objects.create_user(
            "salarie", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.compta,
            responsable_hierarchique=self.chef)


class ResolveursTests(BaseCircuit, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_hierarchie_designe_mon_responsable(self):
        etape = Etape("r", "Responsable", Resolveur.HIERARCHIE)
        self.assertEqual(
            resoudre_acteurs(etape, self.salarie), {self.chef.pk})

    def test_chef_service(self):
        etape = Etape("c", "Chef", Resolveur.CHEF_SERVICE)
        self.assertEqual(
            resoudre_acteurs(etape, self.salarie), {self.chef.pk})

    def test_role_limite_a_la_filiale(self):
        """Un comptable d'une autre filiale n'est pas acteur."""
        etape = Etape("v", "Comptable", Resolveur.ROLE, parametre="COMPTABLE")

        acteurs = resoudre_acteurs(etape, self.salarie)

        self.assertIn(self.comptable_kapi.pk, acteurs)
        self.assertNotIn(self.comptable_oseor.pk, acteurs)

    def test_direction_ignore_la_filiale(self):
        etape = Etape("d", "Direction", Resolveur.DIRECTION)
        self.assertIn(self.dg.pk, resoudre_acteurs(etape, self.salarie))

    def test_repli_quand_personne_n_est_designe(self):
        """Sans responsable, la demande ne doit pas rester sans destinataire."""
        isole = User.objects.create_user(
            "isole", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)
        etape = Etape("r", "Responsable", Resolveur.HIERARCHIE, repli_role="RH")

        self.assertEqual(resoudre_acteurs(etape, isole), {self.rh.pk})

    def test_le_demandeur_est_toujours_exclu(self):
        """Personne ne valide sa propre demande, quel que soit son rôle."""
        etape = Etape("d", "Direction", Resolveur.DIRECTION)
        self.assertNotIn(self.dg.pk, resoudre_acteurs(etape, self.dg))

    def test_responsable_inactif_ignore(self):
        self.chef.is_active = False
        self.chef.save()
        etape = Etape("r", "Responsable", Resolveur.HIERARCHIE)
        self.assertEqual(resoudre_acteurs(etape, self.salarie), set())


class ValidationDirecteTests(BaseCircuit, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.circuit = Circuit(etapes=(
            Etape("responsable", "Responsable", Resolveur.HIERARCHIE),
            Etape("direction", "Direction", Resolveur.DIRECTION, autorite=True),
        ))

    def test_acteur_de_l_etape_ne_saute_rien(self):
        self.assertEqual(
            etapes_sautees(self.circuit, 0, self.chef, self.salarie), [])

    def test_autorite_saute_les_etapes_precedentes(self):
        self.assertEqual(
            etapes_sautees(self.circuit, 0, self.dg, self.salarie),
            ["responsable"],
        )

    def test_sans_autorite_ni_qualite_rien_n_est_permis(self):
        self.assertFalse(
            peut_agir(self.circuit, 0, self.comptable_kapi, self.salarie))

    def test_autorite_habilitee_des_la_premiere_etape(self):
        self.assertTrue(peut_agir(self.circuit, 0, self.dg, self.salarie))

    def test_etape_sans_autorite_ne_saute_pas(self):
        circuit = Circuit(etapes=(
            Etape("a", "A", Resolveur.HIERARCHIE),
            Etape("b", "B", Resolveur.DIRECTION),
        ))
        self.assertFalse(peut_agir(circuit, 0, self.dg, self.salarie))


class EnregistrementTests(BaseCircuit, TestCase):
    """La décision est écrite une fois, avec sa trace complète."""

    def setUp(self):
        self.creer_donnees()
        self.circuit = Circuit(etapes=(
            Etape("responsable", "Responsable", Resolveur.HIERARCHIE),
            Etape("direction", "Direction", Resolveur.DIRECTION, autorite=True),
        ))
        # N'importe quel objet persisté fait l'affaire : le socle est
        # générique, il ne connaît pas les types métier.
        self.objet = self.compta

    def test_avance_d_une_etape(self):
        _, suivante = enregistrer_decision(
            self.objet, self.circuit, 0, self.chef, self.salarie, True)
        self.assertEqual(suivante, 1)

    def test_validation_directe_consomme_les_etapes_sautees(self):
        decision, suivante = enregistrer_decision(
            self.objet, self.circuit, 0, self.dg, self.salarie, True)

        self.assertTrue(decision.validation_directe)
        self.assertEqual(decision.etapes_sautees, ["responsable"])
        self.assertEqual(suivante, 2)

    def test_refus_cloture_le_circuit(self):
        _, suivante = enregistrer_decision(
            self.objet, self.circuit, 0, self.chef, self.salarie, False)
        self.assertEqual(suivante, len(self.circuit))

    def test_non_habilite_refuse(self):
        with self.assertRaises(ValidationRefusee):
            enregistrer_decision(
                self.objet, self.circuit, 0, self.comptable_kapi,
                self.salarie, True)

    def test_demandeur_ne_valide_pas_sa_demande(self):
        with self.assertRaises(ValidationRefusee):
            enregistrer_decision(
                self.objet, self.circuit, 0, self.chef, self.chef, True)

    def test_trace_conservee(self):
        enregistrer_decision(
            self.objet, self.circuit, 0, self.chef, self.salarie, True,
            "d'accord")

        decision = DecisionValidation.objects.get(
            objet_type="Service", objet_id=self.objet.pk)
        self.assertEqual(decision.acteur, self.chef)
        self.assertEqual(decision.etape_cle, "responsable")
        self.assertEqual(decision.commentaire, "d'accord")
        self.assertFalse(decision.validation_directe)

    def test_circuit_epuise(self):
        with self.assertRaises(ValidationRefusee):
            enregistrer_decision(
                self.objet, self.circuit, 5, self.dg, self.salarie, True)


class ObservateursTests(BaseCircuit, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.circuit = Circuit(
            etapes=(Etape("r", "Responsable", Resolveur.HIERARCHIE),),
            observateurs=("RH", "COMPTABLE"),
        )

    def test_observateurs_informes(self):
        envoyees = notifier_observateurs(
            self.compta, self.circuit, "Congé validé", "détail")

        self.assertGreaterEqual(envoyees, 2)
        self.assertTrue(
            Notification.objects.filter(utilisateur=self.rh).exists())
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.comptable_kapi).exists())

    def test_filtrage_par_filiale(self):
        notifier_observateurs(
            self.compta, self.circuit, "Congé validé", "détail",
            filiale_id=self.kapi.pk)

        self.assertFalse(
            Notification.objects.filter(
                utilisateur=self.comptable_oseor).exists())

    def test_exclusion(self):
        """L'intéressé et le décideur ne sont pas notifiés en double."""
        notifier_observateurs(
            self.compta, self.circuit, "Congé validé", "détail",
            exclure=(self.rh,))

        self.assertFalse(
            Notification.objects.filter(utilisateur=self.rh).exists())

    def test_circuit_sans_observateur(self):
        circuit = Circuit(etapes=(Etape("r", "R", Resolveur.HIERARCHIE),))
        self.assertEqual(
            notifier_observateurs(self.compta, circuit, "t", "m"), 0)


class DefinitionCircuitTests(TestCase):
    def test_cles_en_double_refusees(self):
        """Deux étapes homonymes rendraient l'historique illisible."""
        with self.assertRaises(ValueError):
            Circuit(etapes=(
                Etape("a", "A", Resolveur.DIRECTION),
                Etape("a", "A bis", Resolveur.DIRECTION),
            ))

    def test_index_de(self):
        circuit = Circuit(etapes=(
            Etape("a", "A", Resolveur.DIRECTION),
            Etape("b", "B", Resolveur.DIRECTION),
        ))
        self.assertEqual(circuit.index_de("b"), 1)
        self.assertIsNone(circuit.index_de("inconnue"))

    def test_etape_hors_bornes(self):
        circuit = Circuit(etapes=(Etape("a", "A", Resolveur.DIRECTION),))
        self.assertIsNone(circuit.etape(3))
