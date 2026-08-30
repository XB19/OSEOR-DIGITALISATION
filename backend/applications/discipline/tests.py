"""
Procédures disciplinaires — garanties de l'article 58 de la CCIT.

Quatre règles protègent le salarié, et chacune est vérifiée ici :

1. il s'explique **avant** toute sanction ;
2. la sanction respecte le **barème** et ses bornes de durée ;
3. elle intervient dans les **deux mois** de l'établissement de la preuve ;
4. **la même faute ne peut être sanctionnée deux fois**.

Le périmètre de lecture est testé à part : un dossier disciplinaire est la
donnée la plus sensible de l'application.
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from applications.discipline import services
from applications.discipline.convention import TypeSanction, duree_valide
from applications.discipline.models import (
    ExplicationSalarie, ProcedureDisciplinaire, Sanction,
)
from applications.discipline.services import ProcedureRefusee
from applications.filiales.models import Filiale, Service
from applications.notifications.models import Notification

User = get_user_model()


class BaseDiscipline:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")
        self.service = Service.objects.create(
            nom="Informatique", code="IT", filiale=self.kapi)

        self.dg = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)
        self.rh = User.objects.create_user(
            "rh", password="x", role=User.Role.RH, filiale=self.kapi)
        self.rh_oseor = User.objects.create_user(
            "rh_oseor", password="x", role=User.Role.RH, filiale=self.oseor)
        self.chef = User.objects.create_user(
            "chef", password="x", role=User.Role.CHEF_SERVICE,
            filiale=self.kapi, service=self.service)
        self.salarie = User.objects.create_user(
            "salarie", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.service)
        self.collegue = User.objects.create_user(
            "collegue", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.service)

    def ouvrir(self, **surcharges):
        parametres = {
            "salarie": self.salarie,
            "faits": "Absence répétée sans justification.",
            "date_faits": date.today() - timedelta(days=10),
            "date_preuve": date.today() - timedelta(days=5),
            "acteur": self.rh,
        }
        parametres.update(surcharges)
        return services.ouvrir(**parametres)

    def instruire(self, procedure):
        services.consigner_explications(
            procedure, self.rh, ExplicationSalarie.Mode.ECRITE,
            "Je reconnais les faits.")
        procedure.refresh_from_db()
        return procedure


class OuvertureTests(BaseDiscipline, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_reference_et_statut(self):
        procedure = self.ouvrir()
        self.assertTrue(procedure.reference.startswith("KAPI-DISC-"))
        self.assertEqual(procedure.statut, ProcedureDisciplinaire.Statut.OUVERTE)

    def test_seuls_rh_et_direction(self):
        with self.assertRaises(ProcedureRefusee):
            self.ouvrir(acteur=self.chef)

    def test_pas_contre_soi_meme(self):
        with self.assertRaises(ProcedureRefusee):
            self.ouvrir(salarie=self.rh, acteur=self.rh)

    def test_preuve_apres_les_faits(self):
        with self.assertRaises(ProcedureRefusee):
            self.ouvrir(
                date_faits=date.today(),
                date_preuve=date.today() - timedelta(days=3))

    def test_le_salarie_est_informe(self):
        """On ne s'explique pas sur des faits qu'on ignore."""
        self.ouvrir()
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.salarie,
                titre="Procédure disciplinaire ouverte").exists())

    def test_mise_a_pied_conservatoire(self):
        """Mesure d'attente, pas une sanction."""
        procedure = self.ouvrir(mise_a_pied_conservatoire=True)

        self.assertTrue(procedure.mise_a_pied_conservatoire)
        self.assertIsNotNone(procedure.date_mise_a_pied)
        self.assertFalse(hasattr(procedure, "sanction"))


class ExplicationsTests(BaseDiscipline, TestCase):
    """Garantie 1 : le salarié s'explique avant toute sanction."""

    def setUp(self):
        self.creer_donnees()
        self.procedure = self.ouvrir()

    def test_sanction_impossible_sans_explications(self):
        with self.assertRaises(ProcedureRefusee) as erreur:
            services.prononcer(
                self.procedure, self.dg, TypeSanction.AVERTISSEMENT, "motif")

        self.assertIn("explications", str(erreur.exception).lower())

    def test_le_salarie_peut_consigner_les_siennes(self):
        explication = services.consigner_explications(
            self.procedure, self.salarie, ExplicationSalarie.Mode.ECRITE,
            "Voici ma version.")
        self.assertEqual(explication.consignee_par, self.salarie)

    def test_explications_verbales_recevables(self):
        """L'article 58 les admet « écrites ou verbales »."""
        explication = services.consigner_explications(
            self.procedure, self.rh, ExplicationSalarie.Mode.VERBALE,
            "Entendu en présence du délégué.", delegue_present=True)

        self.assertTrue(explication.delegue_present)
        self.procedure.refresh_from_db()
        self.assertTrue(self.procedure.explications_recueillies)

    def test_le_refus_de_s_expliquer_se_consigne(self):
        """
        La garantie est d'avoir été entendu, pas d'avoir parlé : sans cette
        trace, un silence bloquerait la procédure indéfiniment.
        """
        services.consigner_explications(
            self.procedure, self.rh, ExplicationSalarie.Mode.REFUS)

        self.procedure.refresh_from_db()
        self.assertTrue(self.procedure.explications_recueillies)

    def test_contenu_obligatoire_sauf_refus(self):
        with self.assertRaises(ProcedureRefusee):
            services.consigner_explications(
                self.procedure, self.rh, ExplicationSalarie.Mode.ECRITE, "  ")

    def test_un_collegue_ne_consigne_rien(self):
        with self.assertRaises(ProcedureRefusee):
            services.consigner_explications(
                self.procedure, self.collegue, ExplicationSalarie.Mode.ECRITE,
                "ragot")


class BaremeTests(BaseDiscipline, TestCase):
    """Garantie 2 : le barème de l'article 58 et ses bornes."""

    def setUp(self):
        self.creer_donnees()
        self.procedure = self.instruire(self.ouvrir())

    def test_avertissement(self):
        sanction = services.prononcer(
            self.procedure, self.dg, TypeSanction.AVERTISSEMENT,
            "Rappel à l'ordre.")
        self.assertEqual(sanction.type_sanction, TypeSanction.AVERTISSEMENT)

    def test_mise_a_pied_bornee_a_huit_jours(self):
        with self.assertRaises(ProcedureRefusee) as erreur:
            services.prononcer(
                self.procedure, self.dg, TypeSanction.MISE_A_PIED,
                "motif", duree_jours=10)
        self.assertIn("1–8", str(erreur.exception))

    def test_mise_a_pied_aggravee_jusqu_a_quinze(self):
        sanction = services.prononcer(
            self.procedure, self.dg, TypeSanction.MISE_A_PIED_AGGRAVEE,
            "motif", duree_jours=15)
        self.assertEqual(sanction.duree_jours, 15)

    def test_duree_exigee_pour_une_mise_a_pied(self):
        with self.assertRaises(ProcedureRefusee):
            services.prononcer(
                self.procedure, self.dg, TypeSanction.MISE_A_PIED, "motif")

    def test_duree_absurde_sur_un_avertissement(self):
        with self.assertRaises(ProcedureRefusee):
            services.prononcer(
                self.procedure, self.dg, TypeSanction.AVERTISSEMENT,
                "motif", duree_jours=3)

    def test_licenciement_sans_preavis_exige_une_faute_lourde(self):
        """Article 58 e."""
        with self.assertRaises(ProcedureRefusee) as erreur:
            services.prononcer(
                self.procedure, self.dg,
                TypeSanction.LICENCIEMENT_SANS_PREAVIS, "motif")
        self.assertIn("faute lourde", str(erreur.exception).lower())

    def test_licenciement_sans_preavis_sur_faute_lourde(self):
        procedure = self.instruire(self.ouvrir(
            salarie=self.collegue,
            qualification=ProcedureDisciplinaire.Qualification.FAUTE_LOURDE,
            faute_lourde_invoquee="SECRET_PROFESSIONNEL"))

        sanction = services.prononcer(
            procedure, self.dg, TypeSanction.LICENCIEMENT_SANS_PREAVIS,
            "Compromission d'un système de l'entreprise.")

        self.assertEqual(
            sanction.type_sanction, TypeSanction.LICENCIEMENT_SANS_PREAVIS)

    def test_motif_obligatoire(self):
        with self.assertRaises(ProcedureRefusee):
            services.prononcer(
                self.procedure, self.dg, TypeSanction.AVERTISSEMENT, "   ")

    def test_bornes_pures(self):
        self.assertIsNone(duree_valide(TypeSanction.MISE_A_PIED, 8))
        self.assertIsNotNone(duree_valide(TypeSanction.MISE_A_PIED, 9))
        self.assertIsNone(duree_valide(TypeSanction.AVERTISSEMENT, None))


class DelaiTests(BaseDiscipline, TestCase):
    """Garantie 3 : deux mois à compter de l'établissement de la preuve."""

    def setUp(self):
        self.creer_donnees()

    def test_delai_calcule_depuis_la_preuve(self):
        procedure = self.ouvrir(
            date_faits=date(2027, 1, 5), date_preuve=date(2027, 3, 1))

        # La preuve, pas les faits : une faute découverte tard reste
        # sanctionnable.
        self.assertEqual(
            procedure.date_limite_sanction, date(2027, 3, 1) + timedelta(days=60))

    def test_sanction_hors_delai_refusee(self):
        procedure = self.instruire(self.ouvrir(
            date_faits=date.today() - timedelta(days=200),
            date_preuve=date.today() - timedelta(days=180)))

        with self.assertRaises(ProcedureRefusee) as erreur:
            services.prononcer(
                procedure, self.dg, TypeSanction.AVERTISSEMENT, "motif")

        self.assertIn("délai", str(erreur.exception).lower())

    def test_delai_depasse_signale(self):
        procedure = self.ouvrir(
            date_faits=date.today() - timedelta(days=200),
            date_preuve=date.today() - timedelta(days=180))
        self.assertTrue(procedure.delai_depasse)

    def test_alerte_avant_echeance(self):
        procedure = self.ouvrir(
            date_faits=date.today() - timedelta(days=55),
            date_preuve=date.today() - timedelta(days=50))

        envoyees = services.alerter_delais()

        self.assertGreater(envoyees, 0)
        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.rh,
                titre="Délai disciplinaire bientôt expiré").exists())

    def test_pas_d_alerte_sur_un_dossier_recent(self):
        self.ouvrir()
        self.assertEqual(services.alerter_delais(), 0)


class NonBisInIdemTests(BaseDiscipline, TestCase):
    """Garantie 4 : la même faute ne peut être sanctionnée deux fois."""

    def setUp(self):
        self.creer_donnees()
        self.procedure = self.instruire(self.ouvrir())
        services.prononcer(
            self.procedure, self.dg, TypeSanction.AVERTISSEMENT, "premier")
        self.procedure.refresh_from_db()

    def test_seconde_sanction_refusee(self):
        with self.assertRaises(ProcedureRefusee) as erreur:
            services.prononcer(
                self.procedure, self.dg, TypeSanction.MISE_A_PIED,
                "second", duree_jours=3)

        self.assertIn("deux sanctions", str(erreur.exception).lower())

    def test_une_seule_sanction_en_base(self):
        self.assertEqual(
            Sanction.objects.filter(procedure=self.procedure).count(), 1)

    def test_procedure_close(self):
        self.assertEqual(
            self.procedure.statut, ProcedureDisciplinaire.Statut.SANCTIONNEE)


class PrononceTests(BaseDiscipline, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.procedure = self.instruire(self.ouvrir())

    def test_reserve_a_la_direction(self):
        """L'article 58 réserve le prononcé au directeur de l'établissement."""
        with self.assertRaises(ProcedureRefusee) as erreur:
            services.prononcer(
                self.procedure, self.rh, TypeSanction.AVERTISSEMENT, "motif")

        self.assertIn("directeur", str(erreur.exception).lower())

    def test_le_salarie_est_notifie(self):
        services.prononcer(
            self.procedure, self.dg, TypeSanction.AVERTISSEMENT, "motif")

        self.assertTrue(
            Notification.objects.filter(
                utilisateur=self.salarie,
                titre="Sanction disciplinaire").exists())

    def test_formalites_suivies(self):
        """Signification au salarié et ampliation à l'Inspection du Travail."""
        sanction = services.prononcer(
            self.procedure, self.dg, TypeSanction.AVERTISSEMENT, "motif")

        self.assertFalse(sanction.formalites_completes)

        services.enregistrer_formalites(
            sanction, self.rh,
            date_notification=date.today(),
            date_inspection_travail=date.today())

        sanction.refresh_from_db()
        self.assertTrue(sanction.formalites_completes)


class ClassementTests(BaseDiscipline, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.procedure = self.ouvrir(mise_a_pied_conservatoire=True)

    def test_classement_leve_la_mise_a_pied(self):
        services.classer(self.procedure, self.rh, "Faits non établis.")

        self.procedure.refresh_from_db()
        self.assertEqual(
            self.procedure.statut, ProcedureDisciplinaire.Statut.CLASSEE)
        self.assertFalse(self.procedure.mise_a_pied_conservatoire)

    def test_le_dossier_reste_consultable(self):
        """C'est ce qui permet de démontrer qu'il a été classé, et pourquoi."""
        services.classer(self.procedure, self.rh, "Faits non établis.")

        self.procedure.refresh_from_db()
        self.assertEqual(self.procedure.motif_classement, "Faits non établis.")
        self.assertTrue(
            ProcedureDisciplinaire.objects.filter(
                pk=self.procedure.pk).exists())

    def test_motif_obligatoire(self):
        with self.assertRaises(ProcedureRefusee):
            services.classer(self.procedure, self.rh, "  ")

    def test_sanction_impossible_apres_classement(self):
        services.classer(self.procedure, self.rh, "Faits non établis.")
        self.procedure.refresh_from_db()

        with self.assertRaises(ProcedureRefusee):
            services.prononcer(
                self.procedure, self.dg, TypeSanction.AVERTISSEMENT, "motif")


class PerimetreTests(BaseDiscipline, TestCase):
    """
    Le dossier disciplinaire est la donnée la plus sensible : son périmètre
    doit être le plus étroit.
    """

    def setUp(self):
        self.creer_donnees()
        self.procedure = self.ouvrir()

    def _voit(self, utilisateur):
        return services.procedures_visibles(utilisateur).filter(
            pk=self.procedure.pk).exists()

    def test_le_salarie_voit_son_dossier(self):
        self.assertTrue(self._voit(self.salarie))

    def test_les_rh_de_la_filiale(self):
        self.assertTrue(self._voit(self.rh))

    def test_la_direction(self):
        self.assertTrue(self._voit(self.dg))

    def test_un_collegue_ne_voit_rien(self):
        self.assertFalse(self._voit(self.collegue))

    def test_le_chef_de_service_non_plus(self):
        """Même le supérieur hiérarchique n'a pas accès au dossier."""
        self.assertFalse(self._voit(self.chef))

    def test_les_rh_d_une_autre_filiale_non_plus(self):
        self.assertFalse(self._voit(self.rh_oseor))


class DisciplineAPITests(BaseDiscipline, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_ouverture_par_l_api(self):
        self.client.force_authenticate(self.rh)
        reponse = self.client.post("/api/procedures-disciplinaires/", {
            "salarie": self.salarie.pk,
            "faits": "Absences répétées.",
            "date_faits": str(date.today() - timedelta(days=10)),
            "date_preuve": str(date.today() - timedelta(days=5)),
        }, format="json")

        self.assertEqual(reponse.status_code, 201)
        self.assertIn("KAPI-DISC-", reponse.data["reference"])

    def test_un_salarie_ne_peut_pas_ouvrir(self):
        self.client.force_authenticate(self.salarie)
        reponse = self.client.post("/api/procedures-disciplinaires/", {
            "salarie": self.collegue.pk, "faits": "vengeance",
            "date_faits": str(date.today()),
            "date_preuve": str(date.today()),
        }, format="json")

        self.assertEqual(reponse.status_code, 400)

    def test_bareme_expose(self):
        self.client.force_authenticate(self.rh)
        reponse = self.client.get("/api/procedures-disciplinaires/bareme/")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data["delai_mois"], 2)
        self.assertEqual(len(reponse.data["sanctions"]), 5)
        self.assertEqual(len(reponse.data["fautes_lourdes"]), 6)

    def test_un_collegue_ne_liste_rien(self):
        self.ouvrir()

        self.client.force_authenticate(self.collegue)
        reponse = self.client.get("/api/procedures-disciplinaires/")

        self.assertEqual(len(reponse.data.get("results", reponse.data)), 0)

    def test_parcours_complet(self):
        procedure = self.ouvrir()

        self.client.force_authenticate(self.rh)
        self.client.post(
            f"/api/procedures-disciplinaires/{procedure.pk}/demander_explications/")

        self.client.force_authenticate(self.salarie)
        r1 = self.client.post(
            f"/api/procedures-disciplinaires/{procedure.pk}/expliquer/",
            {"mode": "ECRITE", "contenu": "Ma version des faits."},
            format="multipart")
        self.assertEqual(r1.status_code, 201)

        self.client.force_authenticate(self.dg)
        r2 = self.client.post(
            f"/api/procedures-disciplinaires/{procedure.pk}/prononcer/",
            {"type_sanction": "MISE_A_PIED", "motif": "Absences.",
             "duree_jours": 3}, format="json")

        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r2.data["duree_jours"], 3)

    def test_anonyme_refuse(self):
        self.assertIn(
            self.client.get("/api/procedures-disciplinaires/").status_code,
            (401, 403))
