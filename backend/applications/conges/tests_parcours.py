"""
Vie d'un congé après validation : report, rappel, reprise, renoncement.

Deux règles conventionnelles sont vérifiées ici, et ce sont elles qu'un
salarié contestera si elles sont mal appliquées :

- **Article 44b** — un report ne peut excéder trois mois, comptés depuis la
  date initialement fixée ;
- **Article 44d** — les jours travaillés pendant un rappel sont RENDUS au
  salarié, ils ne sont pas perdus.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from applications.conges import parcours, services, workflow
from applications.conges.models import DemandeConge, MouvementConge, TypeConge
from applications.conges.workflow import DemandeRefusee
from applications.filiales.models import Filiale, Service
from applications.notifications.models import Notification

User = get_user_model()


class BaseParcours:
    # Lundi 5 au vendredi 9 juillet 2027 : 5 jours ouvrés.
    DEBUT = date(2027, 7, 5)
    FIN = date(2027, 7, 9)

    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.compta = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.kapi)

        self.dg = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.rh = User.objects.create_user(
            "rh", password="x", role=User.Role.RH, filiale=self.kapi)
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
            date_embauche=date(2023, 1, 10))
        self.collegue = User.objects.create_user(
            "collegue", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)

        services.crediter_acquisitions(self.salarie, date(2027, 7, 1))

    def conge_valide(self):
        demande = workflow.deposer(
            self.salarie, TypeConge.ANNUEL, self.DEBUT, self.FIN)
        workflow.decider(demande, self.chef, approuvee=True)
        workflow.decider(demande, self.dg, approuvee=True)
        demande.refresh_from_db()
        return demande


class ReportTests(BaseParcours, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.demande = self.conge_valide()

    def test_report_decale_la_fenetre_sans_raccourcir(self):
        parcours.reporter(
            self.demande, date(2027, 8, 2), self.chef, "surcroît d'activité")

        self.demande.refresh_from_db()
        self.assertEqual(self.demande.date_debut, date(2027, 8, 2))
        self.assertEqual(self.demande.date_fin, date(2027, 8, 6))
        self.assertEqual(self.demande.jours_ouvres, 5)

    def test_date_initiale_conservee(self):
        """Sans elle, trois reports d'un mois contourneraient le plafond."""
        parcours.reporter(self.demande, date(2027, 8, 2), self.chef, "raison")
        self.demande.refresh_from_db()

        self.assertEqual(self.demande.date_debut_initiale, self.DEBUT)
        self.assertTrue(self.demande.a_ete_reportee)

    def test_plafond_de_trois_mois(self):
        """Article 44b : le départ ne peut être retardé de plus de 3 mois."""
        with self.assertRaises(DemandeRefusee) as erreur:
            parcours.reporter(
                self.demande, date(2027, 11, 8), self.chef, "raison")

        self.assertIn("trois mois", str(erreur.exception).lower()
                      .replace("3 mois", "trois mois"))

    def test_plafond_compte_depuis_la_date_initiale(self):
        """Deux reports successifs ne doivent pas dépasser le plafond."""
        parcours.reporter(self.demande, date(2027, 9, 6), self.chef, "raison")
        self.demande.refresh_from_db()

        with self.assertRaises(DemandeRefusee):
            parcours.reporter(
                self.demande, date(2027, 11, 1), self.chef, "encore")

    def test_report_ne_peut_pas_avancer_le_depart(self):
        with self.assertRaises(DemandeRefusee):
            parcours.reporter(
                self.demande, date(2027, 6, 1), self.chef, "raison")

    def test_motif_obligatoire(self):
        """Le salarié doit savoir pourquoi son départ est décalé."""
        with self.assertRaises(DemandeRefusee):
            parcours.reporter(self.demande, date(2027, 8, 2), self.chef, "  ")

    def test_le_salarie_ne_reporte_pas_son_propre_conge(self):
        with self.assertRaises(DemandeRefusee):
            parcours.reporter(
                self.demande, date(2027, 8, 2), self.salarie, "envie")

    def test_un_collegue_non_plus(self):
        with self.assertRaises(DemandeRefusee):
            parcours.reporter(
                self.demande, date(2027, 8, 2), self.collegue, "raison")

    def test_le_salarie_est_prevenu(self):
        parcours.reporter(self.demande, date(2027, 8, 2), self.chef, "raison")

        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.salarie, titre="Congé reporté").exists())

    def test_solde_ajuste_si_le_decompte_change(self):
        """
        Un report qui enjambe un férié ne doit pas coûter un jour de plus.
        Le 15 août est férié : la semaine du 16 en compte 5, celle du 9 aussi,
        mais une fenêtre incluant le 15 n'en compte que 4.
        """
        from applications.conges.models import JourFerie

        JourFerie.objects.create(
            date=date(2027, 8, 4), nom="Férié de test", filiale=None)
        avant = services.solde(self.salarie)

        parcours.reporter(self.demande, date(2027, 8, 2), self.chef, "raison")

        self.demande.refresh_from_db()
        self.assertEqual(self.demande.jours_ouvres, 4)
        # Un jour de moins consommé : le solde remonte d'autant.
        self.assertEqual(services.solde(self.salarie), avant + 1)


class RappelTests(BaseParcours, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.demande = self.conge_valide()

    def test_rappel_interrompt_sans_annuler(self):
        parcours.rappeler(
            self.demande, self.chef, "incident serveur", date(2027, 7, 7))

        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, DemandeConge.Statut.INTERROMPUE)
        self.assertEqual(self.demande.date_rappel, date(2027, 7, 7))
        self.assertEqual(self.demande.rappele_par, self.chef)

    def test_rappel_hors_periode_refuse(self):
        with self.assertRaises(DemandeRefusee):
            parcours.rappeler(
                self.demande, self.chef, "raison", date(2027, 9, 1))

    def test_motif_obligatoire(self):
        with self.assertRaises(DemandeRefusee):
            parcours.rappeler(self.demande, self.chef, "", date(2027, 7, 7))

    def test_le_salarie_ne_se_rappelle_pas_lui_meme(self):
        with self.assertRaises(DemandeRefusee):
            parcours.rappeler(
                self.demande, self.salarie, "raison", date(2027, 7, 7))

    def test_solde_inchange_tant_que_le_choix_n_est_pas_fait(self):
        avant = services.solde(self.salarie)
        parcours.rappeler(
            self.demande, self.chef, "urgence", date(2027, 7, 7))
        self.assertEqual(services.solde(self.salarie), avant)

    def test_le_salarie_est_prevenu(self):
        parcours.rappeler(
            self.demande, self.chef, "urgence", date(2027, 7, 7))
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.salarie, titre="Rappel en service").exists())


class RepriseTests(BaseParcours, TestCase):
    """Article 44d : les jours travaillés pendant le rappel sont rendus."""

    def setUp(self):
        self.creer_donnees()
        self.demande = self.conge_valide()
        parcours.rappeler(
            self.demande, self.chef, "urgence", date(2027, 7, 7))
        self.demande.refresh_from_db()

    def test_le_conge_est_prolonge_des_jours_travailles(self):
        # Rappelé le mercredi 7, reprend le congé le vendredi 9 :
        # 7 et 8 travaillés (2 jours ouvrés) → fin repoussée de 2 jours ouvrés.
        parcours.reprendre(self.demande, self.salarie, date(2027, 7, 8))

        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, DemandeConge.Statut.VALIDEE)
        self.assertEqual(self.demande.date_fin, date(2027, 7, 13))

    def test_le_decompte_ne_change_pas(self):
        """Le salarié ne consomme pas plus : il récupère ce qu'on lui a pris."""
        avant = services.solde(self.salarie)

        parcours.reprendre(self.demande, self.salarie, date(2027, 7, 8))

        self.assertEqual(services.solde(self.salarie), avant)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.jours_ouvres, 5)

    def test_reprise_avant_le_rappel_refusee(self):
        with self.assertRaises(DemandeRefusee):
            parcours.reprendre(self.demande, self.chef, date(2027, 7, 6))

    def test_conge_non_interrompu(self):
        demande = DemandeConge.objects.create(
            utilisateur=self.salarie, type_conge=TypeConge.ANNUEL,
            date_debut=date(2027, 9, 6), date_fin=date(2027, 9, 10),
            jours_ouvres=5, statut=DemandeConge.Statut.VALIDEE)
        with self.assertRaises(DemandeRefusee):
            parcours.reprendre(demande, self.chef)

    def test_le_salarie_est_prevenu_de_la_prolongation(self):
        parcours.reprendre(self.demande, self.salarie, date(2027, 7, 8))
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.salarie, titre="Congé prolongé").exists())


class RenoncementTests(BaseParcours, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.demande = self.conge_valide()
        parcours.rappeler(
            self.demande, self.chef, "urgence", date(2027, 7, 7))
        self.demande.refresh_from_db()

    def test_les_jours_non_pris_sont_recredites(self):
        # Congé du 5 au 9 (5 j), rappelé le 7 : 5 et 6 pris (2 j),
        # donc 3 jours doivent revenir au solde.
        avant = services.solde(self.salarie)

        parcours.renoncer_au_reliquat(self.demande, self.salarie)

        self.demande.refresh_from_db()
        self.assertEqual(self.demande.jours_ouvres, 2)
        self.assertEqual(self.demande.statut, DemandeConge.Statut.TERMINEE)
        self.assertEqual(services.solde(self.salarie), avant + 3)

    def test_correction_tracee_au_registre(self):
        """Une correction s'ajoute au registre, elle ne le réécrit pas."""
        parcours.renoncer_au_reliquat(self.demande, self.salarie)

        correction = MouvementConge.objects.filter(
            demande=self.demande,
            type_mouvement=MouvementConge.TypeMouvement.CORRECTION).first()

        self.assertIsNotNone(correction)
        self.assertEqual(correction.jours, Decimal("3"))

    def test_date_de_fin_ramenee_a_la_veille_du_rappel(self):
        parcours.renoncer_au_reliquat(self.demande, self.salarie)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.date_fin, date(2027, 7, 6))

    def test_un_collegue_ne_peut_pas_ecourter(self):
        with self.assertRaises(DemandeRefusee):
            parcours.renoncer_au_reliquat(self.demande, self.collegue)

    def test_le_salarie_est_prevenu(self):
        parcours.renoncer_au_reliquat(self.demande, self.salarie)
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.salarie, titre="Congé écourté").exists())


class RappelDepartTests(BaseParcours, TestCase):
    """Rappel de veille : le salarié, son valideur et les observateurs."""

    def setUp(self):
        self.creer_donnees()
        self.demande = self.conge_valide()

    def test_prevenu_la_veille(self):
        envoyes = services.rappeler_departs_imminents(
            jour=self.DEBUT - timedelta(days=1))

        self.assertGreater(envoyes, 0)
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.salarie,
                titre="Départ en congé demain").exists())

    def test_le_valideur_est_prevenu(self):
        services.rappeler_departs_imminents(jour=self.DEBUT - timedelta(days=1))
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.demande.valideur,
                titre="Départ en congé demain").exists())

    def test_les_rh_sont_prevenus(self):
        services.rappeler_departs_imminents(jour=self.DEBUT - timedelta(days=1))
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.rh, titre="Départ en congé demain").exists())

    def test_aucun_depart_aucun_envoi(self):
        self.assertEqual(
            services.rappeler_departs_imminents(jour=date(2027, 1, 5)), 0)

    def test_conge_non_valide_ignore(self):
        DemandeConge.objects.create(
            utilisateur=self.collegue, type_conge=TypeConge.ANNUEL,
            date_debut=date(2027, 10, 4), date_fin=date(2027, 10, 8),
            jours_ouvres=5, statut=DemandeConge.Statut.EN_ATTENTE)

        envoyes = services.rappeler_departs_imminents(jour=date(2027, 10, 3))

        self.assertEqual(envoyes, 0)


class ParcoursAPITests(BaseParcours, APITestCase):
    def setUp(self):
        self.creer_donnees()
        self.demande = self.conge_valide()

    def test_reporter(self):
        self.client.force_authenticate(self.chef)
        reponse = self.client.post(
            f"/api/conges/{self.demande.pk}/reporter/",
            {"date_debut": "2027-08-02", "motif": "surcroît d'activité"},
            format="json")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data["date_debut"], "2027-08-02")

    def test_reporter_au_dela_du_plafond(self):
        self.client.force_authenticate(self.chef)
        reponse = self.client.post(
            f"/api/conges/{self.demande.pk}/reporter/",
            {"date_debut": "2027-12-06", "motif": "raison"}, format="json")

        self.assertEqual(reponse.status_code, 400)

    def test_rappeler_puis_reprendre(self):
        self.client.force_authenticate(self.chef)
        r1 = self.client.post(
            f"/api/conges/{self.demande.pk}/rappeler/",
            {"motif": "incident", "jour": "2027-07-07"}, format="json")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data["statut"], DemandeConge.Statut.INTERROMPUE)

        self.client.force_authenticate(self.salarie)
        r2 = self.client.post(
            f"/api/conges/{self.demande.pk}/reprendre/",
            {"jour": "2027-07-08"}, format="json")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data["statut"], DemandeConge.Statut.VALIDEE)

    def test_ecourter(self):
        self.client.force_authenticate(self.chef)
        self.client.post(
            f"/api/conges/{self.demande.pk}/rappeler/",
            {"motif": "incident", "jour": "2027-07-07"}, format="json")

        self.client.force_authenticate(self.salarie)
        reponse = self.client.post(
            f"/api/conges/{self.demande.pk}/ecourter/", {}, format="json")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data["statut"], DemandeConge.Statut.TERMINEE)
        self.assertEqual(reponse.data["jours_ouvres"], 2)
