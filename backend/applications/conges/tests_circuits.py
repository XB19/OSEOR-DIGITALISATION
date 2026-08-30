"""
Choix du circuit selon le demandeur et le type de congé.

Trois situations distinctes, et il ne faut pas les confondre : un salarié
passe par son responsable puis la direction, un directeur n'ayant pas de
supérieur passe par les RH, et une permission de droit ne se fait pas
arbitrer par le Directeur Général.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from applications.conges import services, workflow
from applications.conges.circuits import (
    CIRCUIT_DIRECTION, CIRCUIT_PERMISSION, CIRCUIT_SALARIE, circuit_pour,
)
from applications.conges.convention import MotifPermission
from applications.conges.models import DemandeConge, TypeConge
from applications.filiales.models import Filiale, Service
from applications.notifications.models import Notification

User = get_user_model()


class BaseCircuits:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.compta = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.kapi)

        self.dg = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi,
            date_embauche=date(2020, 1, 6))
        self.autre_dg = User.objects.create_user(
            "dg2", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.rh = User.objects.create_user(
            "rh", password="x", role=User.Role.RH, filiale=self.kapi)
        self.comptable = User.objects.create_user(
            "comptable", password="x", role=User.Role.COMPTABLE, filiale=self.kapi)

        self.chef = User.objects.create_user(
            "chef", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.compta,
            responsable_hierarchique=self.dg)
        self.compta.chef = self.chef
        self.compta.save()

        self.salarie = User.objects.create_user(
            "salarie", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.compta,
            responsable_hierarchique=self.chef,
            date_embauche=date(2024, 1, 15))

        services.crediter_acquisitions(self.salarie, date(2027, 7, 1))
        services.crediter_acquisitions(self.dg, date(2027, 7, 1))

    DEBUT = date(2027, 7, 5)
    FIN = date(2027, 7, 9)


class ChoixDuCircuitTests(BaseCircuits, TestCase):
    def setUp(self):
        self.creer_donnees()

    def _demande(self, utilisateur, type_conge=TypeConge.ANNUEL, motif=""):
        return DemandeConge(
            utilisateur=utilisateur, type_conge=type_conge,
            motif_permission=motif,
            date_debut=self.DEBUT, date_fin=self.FIN, jours_ouvres=5)

    def test_salarie(self):
        self.assertIs(circuit_pour(self._demande(self.salarie)), CIRCUIT_SALARIE)

    def test_directeur(self):
        """Un DG n'a pas de supérieur : sa demande part aux RH."""
        self.assertIs(circuit_pour(self._demande(self.dg)), CIRCUIT_DIRECTION)

    def test_administrateur_traite_comme_la_direction(self):
        admin = User.objects.create_user(
            "admin", password="x", role=User.Role.ADMINISTRATEUR,
            filiale=self.kapi)
        self.assertIs(circuit_pour(self._demande(admin)), CIRCUIT_DIRECTION)

    def test_permission_familiale(self):
        """Un droit conventionnel ne s'arbitre pas par la direction."""
        demande = self._demande(
            self.salarie, TypeConge.PERMISSION, MotifPermission.DECES_FRERE_SOEUR)
        self.assertIs(circuit_pour(demande), CIRCUIT_PERMISSION)

    def test_permission_syndicale_suit_le_circuit_complet(self):
        """10 jours de congrès : long et discrétionnaire, donc deux étapes."""
        demande = self._demande(
            self.salarie, TypeConge.PERMISSION, MotifPermission.CONGRES_SYNDICAL)
        self.assertIs(circuit_pour(demande), CIRCUIT_SALARIE)


class CircuitDirectionTests(BaseCircuits, TestCase):
    """Parcours réel d'une demande de directeur."""

    def setUp(self):
        self.creer_donnees()
        self.demande = workflow.deposer(
            self.dg, TypeConge.ANNUEL, self.DEBUT, self.FIN)

    def test_les_rh_sont_sollicites(self):
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.rh, titre="Demande de congé à valider").exists())

    def test_les_rh_peuvent_trancher(self):
        self.assertTrue(workflow.peut_valider(self.demande, self.rh))

    def test_un_salarie_ne_peut_pas(self):
        self.assertFalse(workflow.peut_valider(self.demande, self.salarie))

    def test_le_dg_ne_valide_pas_sa_propre_demande(self):
        self.assertFalse(workflow.peut_valider(self.demande, self.dg))

    def test_les_rh_concluent_seuls(self):
        """L'étape RH porte l'autorité : elle peut clore le circuit."""
        workflow.decider(self.demande, self.rh, approuvee=True)
        self.assertEqual(self.demande.statut, DemandeConge.Statut.VALIDEE)

    def test_un_autre_directeur_peut_conclure(self):
        workflow.decider(self.demande, self.autre_dg, approuvee=True)
        self.assertEqual(self.demande.statut, DemandeConge.Statut.VALIDEE)


class CircuitPermissionTests(BaseCircuits, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_le_responsable_suffit(self):
        """Une permission de droit se règle en une étape."""
        demande = workflow.deposer(
            self.salarie, TypeConge.PERMISSION,
            date(2027, 8, 2), date(2027, 8, 3),
            motif_permission=MotifPermission.DECES_FRERE_SOEUR)

        workflow.decider(demande, self.chef, approuvee=True)

        self.assertEqual(demande.statut, DemandeConge.Statut.VALIDEE)

    def test_solde_annuel_intact(self):
        """Article 45 : non déductible du congé annuel."""
        avant = services.solde(self.salarie)

        demande = workflow.deposer(
            self.salarie, TypeConge.PERMISSION,
            date(2027, 8, 2), date(2027, 8, 3),
            motif_permission=MotifPermission.DECES_FRERE_SOEUR)
        workflow.decider(demande, self.chef, approuvee=True)

        self.assertEqual(services.solde(self.salarie), avant)
