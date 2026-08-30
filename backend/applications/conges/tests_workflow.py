"""
Parcours d'une demande de congé : dépôt, validation, refus, annulation.

Le point sensible est la désignation du valideur : contrairement à la
chaîne de visas des documents, qui s'adresse à un RÔLE, un congé se valide
par **mon** responsable. Un chef de service d'une autre équipe ne doit pas
pouvoir trancher.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from applications.conges import services, workflow
from applications.conges.models import DemandeConge, MouvementConge, TypeConge
from applications.conges.workflow import DemandeRefusee
from applications.filiales.models import Filiale, Service
from applications.notifications.models import Notification

User = get_user_model()


class BaseWorkflow:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.compta = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.kapi)
        self.logistique = Service.objects.create(
            nom="Logistique", code="LOG", filiale=self.kapi)

        self.directeur = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.rh = User.objects.create_user(
            "rh", password="x", role=User.Role.RH, filiale=self.kapi)

        self.chef = User.objects.create_user(
            "chef", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.compta,
            responsable_hierarchique=self.directeur,
            date_embauche=date(2024, 1, 10))
        self.compta.chef = self.chef
        self.compta.save()

        self.autre_chef = User.objects.create_user(
            "autre_chef", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.logistique)
        self.logistique.chef = self.autre_chef
        self.logistique.save()

        self.salarie = User.objects.create_user(
            "salarie", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.compta,
            responsable_hierarchique=self.chef,
            date_embauche=date(2025, 1, 10))

        # Solde confortable : 12 mois révolus.
        services.crediter_acquisitions(self.salarie, date(2026, 1, 10))

    # Lundi 5 au vendredi 9 juillet 2027 : 5 jours ouvrés.
    DEBUT = date(2027, 7, 5)
    FIN = date(2027, 7, 9)

    def deposer(self, **surcharges):
        parametres = {
            "utilisateur": self.salarie,
            "type_conge": TypeConge.ANNUEL,
            "date_debut": self.DEBUT,
            "date_fin": self.FIN,
        }
        parametres.update(surcharges)
        return workflow.deposer(**parametres)


class DepotTests(BaseWorkflow, TestCase):
    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.salarie, date(2027, 7, 10))

    def test_jours_ouvres_calcules(self):
        demande = self.deposer()
        self.assertEqual(demande.jours_ouvres, 5)
        self.assertEqual(demande.statut, DemandeConge.Statut.EN_ATTENTE)

    def test_periode_sans_jour_ouvre_refusee(self):
        """Un week-end ne se pose pas en congé."""
        with self.assertRaises(DemandeRefusee):
            self.deposer(date_debut=date(2027, 7, 10), date_fin=date(2027, 7, 11))

    def test_dates_inversees_refusees(self):
        with self.assertRaises(DemandeRefusee):
            self.deposer(date_debut=self.FIN, date_fin=self.DEBUT)

    def test_chevauchement_refuse(self):
        self.deposer()
        with self.assertRaises(DemandeRefusee) as erreur:
            self.deposer(date_debut=date(2027, 7, 7), date_fin=date(2027, 7, 13))
        self.assertIn("déjà une demande", str(erreur.exception))

    def test_solde_insuffisant_refuse(self):
        maigre = User.objects.create_user(
            "maigre", password="x", role=User.Role.EMPLOYE, filiale=self.kapi,
            responsable_hierarchique=self.chef, date_embauche=date(2027, 5, 1))
        services.crediter_acquisitions(maigre, date(2027, 6, 1))  # 2,5 j

        with self.assertRaises(DemandeRefusee) as erreur:
            self.deposer(utilisateur=maigre)
        self.assertIn("Solde insuffisant", str(erreur.exception))

    def test_maladie_ne_verifie_pas_le_solde(self):
        maigre = User.objects.create_user(
            "maigre", password="x", role=User.Role.EMPLOYE, filiale=self.kapi,
            responsable_hierarchique=self.chef, date_embauche=date(2027, 5, 1))

        demande = self.deposer(utilisateur=maigre, type_conge=TypeConge.MALADIE)

        self.assertEqual(demande.jours_ouvres, 5)

    def test_le_responsable_est_notifie(self):
        self.deposer()
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.chef, titre="Demande de congé à valider").exists())

    def test_repli_sur_les_rh_sans_responsable(self):
        """Sans responsable ni chef de service, les RH prennent le relais."""
        isole = User.objects.create_user(
            "isole", password="x", role=User.Role.EMPLOYE, filiale=self.kapi,
            date_embauche=date(2025, 1, 1))
        services.crediter_acquisitions(isole, date(2027, 7, 1))

        self.deposer(utilisateur=isole)

        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.rh, titre="Demande de congé à valider").exists())

    def test_solde_non_debite_avant_validation(self):
        avant = services.solde(self.salarie, 2027)
        self.deposer()
        self.assertEqual(services.solde(self.salarie, 2027), avant)


class ValidationTests(BaseWorkflow, TestCase):
    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.salarie, date(2027, 7, 10))
        self.demande = self.deposer()

    def test_le_responsable_direct_valide(self):
        self.assertTrue(workflow.peut_valider(self.demande, self.chef))

    def test_un_chef_d_une_autre_equipe_ne_valide_pas(self):
        """
        Différence essentielle avec les visas documentaires : ce n'est pas
        le rôle qui compte, c'est le lien hiérarchique.
        """
        self.assertFalse(workflow.peut_valider(self.demande, self.autre_chef))

    def test_direction_peut_valider_directement(self):
        """
        La direction porte l'autorité du circuit : elle peut trancher sans
        attendre le responsable hiérarchique.
        """
        self.assertTrue(workflow.peut_valider(self.demande, self.directeur))

    def test_rh_n_est_plus_valideur_d_un_salarie_encadre(self):
        """
        Nouveau circuit : responsable puis direction. Les RH sont
        observateurs, pas décideurs — sauf en repli, quand le salarié n'a
        aucun responsable désigné.
        """
        self.assertFalse(workflow.peut_valider(self.demande, self.rh))

    def test_nul_ne_valide_sa_propre_demande(self):
        services.crediter_acquisitions(self.chef, date(2027, 8, 1))
        sienne = workflow.deposer(
            self.chef, TypeConge.ANNUEL, date(2027, 8, 2), date(2027, 8, 6))
        self.assertFalse(workflow.peut_valider(sienne, self.chef))

    def test_le_responsable_seul_ne_cloture_pas(self):
        """
        Le circuit demande l'accord du responsable PUIS de la direction :
        une seule signature ne suffit pas, et le solde n'est pas encore
        débité.
        """
        avant = services.solde(self.salarie, 2027)

        workflow.decider(self.demande, self.chef, approuvee=True)

        self.assertEqual(self.demande.statut, DemandeConge.Statut.EN_ATTENTE)
        self.assertEqual(services.solde(self.salarie, 2027), avant)

    def test_validation_complete_debite_le_solde(self):
        avant = services.solde(self.salarie, 2027)

        workflow.decider(self.demande, self.chef, approuvee=True)
        workflow.decider(self.demande, self.directeur, approuvee=True)

        self.assertEqual(self.demande.statut, DemandeConge.Statut.VALIDEE)
        self.assertEqual(services.solde(self.salarie, 2027), avant - 5)

    def test_validation_directe_de_la_direction(self):
        """
        La direction conclut seule ; les étapes sautées sont consignées.
        """
        from applications.validation.models import DecisionValidation

        avant = services.solde(self.salarie, 2027)

        workflow.decider(self.demande, self.directeur, approuvee=True)

        self.assertEqual(self.demande.statut, DemandeConge.Statut.VALIDEE)
        self.assertEqual(services.solde(self.salarie, 2027), avant - 5)

        decision = DecisionValidation.objects.get(
            objet_type="DemandeConge", objet_id=self.demande.pk)
        self.assertTrue(decision.validation_directe)
        self.assertEqual(decision.etapes_sautees, ["responsable"])

    def test_refus_ne_debite_pas(self):
        avant = services.solde(self.salarie, 2027)

        workflow.decider(self.demande, self.chef, approuvee=False, motif="Période chargée")

        self.assertEqual(services.solde(self.salarie, 2027), avant)
        self.assertEqual(self.demande.statut, DemandeConge.Statut.REFUSEE)
        self.assertEqual(self.demande.motif_decision, "Période chargée")

    def test_demande_deja_traitee(self):
        workflow.decider(self.demande, self.chef, approuvee=True)
        workflow.decider(self.demande, self.directeur, approuvee=True)

        with self.assertRaises(DemandeRefusee):
            workflow.decider(self.demande, self.directeur, approuvee=False)

    def test_non_habilite_refuse(self):
        with self.assertRaises(DemandeRefusee):
            workflow.decider(self.demande, self.autre_chef, approuvee=True)

    def test_le_salarie_est_notifie_a_la_cloture(self):
        """Le salarié est prévenu quand la décision est définitive."""
        workflow.decider(self.demande, self.chef, approuvee=True)
        self.assertFalse(
            Notification.objects.filter(
                utilisateur=self.salarie, titre="Congé validé").exists())

        workflow.decider(self.demande, self.directeur, approuvee=True)
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.salarie, titre="Congé validé").exists())

    def test_observateurs_informes(self):
        """RH et comptabilité reçoivent l'information complète."""
        workflow.decider(self.demande, self.chef, approuvee=True)
        workflow.decider(self.demande, self.directeur, approuvee=True)

        avis = Notification.objects.filter(
            utilisateur=self.rh, titre="Congé validé").first()

        self.assertIsNotNone(avis)
        self.assertIn(self.salarie.nom_complet, avis.message)
        self.assertIn("5 j", avis.message)


class AnnulationTests(BaseWorkflow, TestCase):
    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.salarie, date(2027, 7, 10))
        self.demande = self.deposer()

    def test_annulation_apres_validation_restitue(self):
        avant = services.solde(self.salarie, 2027)
        workflow.decider(self.demande, self.chef, approuvee=True)

        workflow.annuler(self.demande, self.salarie)

        self.assertEqual(services.solde(self.salarie, 2027), avant)
        self.assertEqual(self.demande.statut, DemandeConge.Statut.ANNULEE)

    def test_annulation_avant_validation_ne_restitue_rien(self):
        avant = services.solde(self.salarie, 2027)

        workflow.annuler(self.demande, self.salarie)

        self.assertEqual(services.solde(self.salarie, 2027), avant)
        self.assertFalse(
            MouvementConge.objects.filter(
                demande=self.demande,
                type_mouvement=MouvementConge.TypeMouvement.RESTITUTION).exists())

    def test_libere_la_periode(self):
        """Après annulation, la même période redevient posable."""
        workflow.annuler(self.demande, self.salarie)
        nouvelle = self.deposer()
        self.assertEqual(nouvelle.jours_ouvres, 5)

    def test_un_tiers_ne_peut_pas_annuler(self):
        with self.assertRaises(DemandeRefusee):
            workflow.annuler(self.demande, self.autre_chef)

    def test_rh_peut_annuler(self):
        workflow.annuler(self.demande, self.rh, motif="Erreur de saisie")
        self.assertEqual(self.demande.statut, DemandeConge.Statut.ANNULEE)

    def test_demande_deja_annulee(self):
        workflow.annuler(self.demande, self.salarie)
        with self.assertRaises(DemandeRefusee):
            workflow.annuler(self.demande, self.salarie)


class CongeAPITests(BaseWorkflow, APITestCase):
    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.salarie, date(2027, 7, 10))

    def test_depot_par_l_api(self):
        self.client.force_authenticate(self.salarie)
        reponse = self.client.post("/api/conges/", {
            "type_conge": TypeConge.ANNUEL,
            "date_debut": "2027-07-05",
            "date_fin": "2027-07-09",
        }, format="json")

        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse.data["jours_ouvres"], 5)

    def test_solde_insuffisant_renvoie_400_explicite(self):
        self.client.force_authenticate(self.salarie)
        reponse = self.client.post("/api/conges/", {
            "type_conge": TypeConge.ANNUEL,
            "date_debut": "2027-07-05",
            "date_fin": "2027-12-31",
        }, format="json")

        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Solde insuffisant", reponse.data["detail"])

    def test_perimetre_de_lecture(self):
        """Un salarié ne voit que ses demandes ; son chef voit les siennes."""
        self.deposer()

        self.client.force_authenticate(self.autre_chef)
        reponse = self.client.get("/api/conges/")
        self.assertEqual(len(reponse.data.get("results", reponse.data)), 0)

        self.client.force_authenticate(self.chef)
        reponse = self.client.get("/api/conges/")
        self.assertEqual(len(reponse.data.get("results", reponse.data)), 1)

    def test_rh_voit_tout(self):
        self.deposer()
        self.client.force_authenticate(self.rh)
        reponse = self.client.get("/api/conges/")
        self.assertEqual(len(reponse.data.get("results", reponse.data)), 1)

    def test_decider_par_l_api(self):
        demande = self.deposer()

        self.client.force_authenticate(self.chef)
        r1 = self.client.post(
            f"/api/conges/{demande.pk}/decider/",
            {"approuvee": True}, format="json")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data["statut"], DemandeConge.Statut.EN_ATTENTE)

        self.client.force_authenticate(self.directeur)
        r2 = self.client.post(
            f"/api/conges/{demande.pk}/decider/",
            {"approuvee": True}, format="json")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data["statut"], DemandeConge.Statut.VALIDEE)

    def test_mon_solde(self):
        self.client.force_authenticate(self.salarie)
        reponse = self.client.get("/api/conges/mon_solde/?annee=2027")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Decimal(reponse.data["acquis"]), Decimal("17.5"))

    def test_mon_registre(self):
        self.client.force_authenticate(self.salarie)
        reponse = self.client.get("/api/conges/mon_registre/?annee=2027")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.data), 7)  # janv. à juil. 2027

    def test_a_valider(self):
        self.deposer()

        self.client.force_authenticate(self.chef)
        reponse = self.client.get("/api/conges/a_valider/")
        self.assertEqual(len(reponse.data), 1)

        self.client.force_authenticate(self.autre_chef)
        reponse = self.client.get("/api/conges/a_valider/")
        self.assertEqual(len(reponse.data), 0)

    def test_modification_directe_impossible(self):
        """Une demande est un parcours de décisions tracées, pas un formulaire."""
        demande = self.deposer()
        self.client.force_authenticate(self.salarie)
        self.assertEqual(
            self.client.put(f"/api/conges/{demande.pk}/", {}).status_code, 405)

    def test_anonyme_refuse(self):
        self.assertIn(self.client.get("/api/conges/").status_code, (401, 403))
