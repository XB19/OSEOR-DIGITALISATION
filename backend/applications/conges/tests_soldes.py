"""
Soldes de congés : acquisition mensuelle depuis la date d'embauche,
réservation par les demandes en attente, expiration au 31 décembre.

C'est ici que se joue le risque principal du module : un jour crédité deux
fois ou perdu à tort est un litige avec un salarié. L'idempotence de
l'acquisition est donc testée explicitement — la tâche est rejouable par
conception (ACKS_LATE).
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from applications.conges import services
from applications.conges.models import DemandeConge, MouvementConge, TypeConge
from applications.conges.tasks import crediter_acquisitions as tache_acquisition
from applications.filiales.models import Filiale

User = get_user_model()


class BaseSoldes:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.salarie = User.objects.create_user(
            "salarie", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, date_embauche=date(2026, 9, 15))


class EcheancesTests(TestCase):
    """Fonction pure : quand tombent les acquisitions."""

    def test_premier_mois_revolu(self):
        """Entré le 15 septembre, premiers jours acquis le 15 octobre."""
        echeances = services.echeances_acquisition(
            date(2026, 9, 15), date(2026, 10, 15))
        self.assertEqual(echeances, [date(2026, 10, 15)])

    def test_rien_avant_un_mois_complet(self):
        self.assertEqual(
            services.echeances_acquisition(date(2026, 9, 15), date(2026, 10, 14)),
            [],
        )

    def test_passage_d_annee(self):
        echeances = services.echeances_acquisition(
            date(2026, 11, 10), date(2027, 2, 10))
        self.assertEqual(
            echeances,
            [date(2026, 12, 10), date(2027, 1, 10), date(2027, 2, 10)],
        )

    def test_embauche_en_fin_de_mois(self):
        """
        Une embauche le 31 janvier n'a pas de 31 février : l'échéance est
        ramenée au dernier jour du mois, sinon ces salariés seraient
        privés d'acquisition certains mois.
        """
        echeances = services.echeances_acquisition(
            date(2027, 1, 31), date(2027, 4, 30))
        self.assertEqual(
            echeances,
            [date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)],
        )

    def test_sans_date_d_embauche(self):
        self.assertEqual(
            services.echeances_acquisition(None, date(2027, 1, 1)), [])

    def test_date_anterieure_a_l_embauche(self):
        self.assertEqual(
            services.echeances_acquisition(date(2027, 6, 1), date(2027, 1, 1)), [])

    def test_douze_mois_donnent_trente_jours(self):
        """La règle des 30 jours annuels doit tomber juste."""
        echeances = services.echeances_acquisition(
            date(2026, 1, 1), date(2027, 1, 1))
        self.assertEqual(len(echeances), 12)
        self.assertEqual(
            len(echeances) * services.ACQUISITION_MENSUELLE,
            services.PLAFOND_ANNUEL,
        )


class AcquisitionTests(BaseSoldes, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_credite_les_echeances_echues(self):
        cree = services.crediter_acquisitions(self.salarie, date(2026, 12, 15))

        self.assertEqual(cree, 3)  # 15/10, 15/11, 15/12
        self.assertEqual(services.solde(self.salarie, 2026), Decimal("7.5"))

    def test_idempotente(self):
        """Rejouer la tâche ne doit jamais créditer deux fois."""
        services.crediter_acquisitions(self.salarie, date(2026, 12, 15))
        services.crediter_acquisitions(self.salarie, date(2026, 12, 15))
        services.crediter_acquisitions(self.salarie, date(2026, 12, 15))

        self.assertEqual(services.solde(self.salarie, 2026), Decimal("7.5"))
        self.assertEqual(
            MouvementConge.objects.filter(
                utilisateur=self.salarie,
                type_mouvement=MouvementConge.TypeMouvement.ACQUISITION,
            ).count(),
            3,
        )

    def test_reprise_apres_interruption(self):
        """Une exécution partielle est rattrapée au passage suivant."""
        services.crediter_acquisitions(self.salarie, date(2026, 11, 15))
        self.assertEqual(services.solde(self.salarie, 2026), Decimal("5"))

        services.crediter_acquisitions(self.salarie, date(2027, 1, 15))

        self.assertEqual(services.solde(self.salarie, 2026), Decimal("7.5"))
        self.assertEqual(services.solde(self.salarie, 2027), Decimal("2.5"))

    def test_rattachement_a_la_bonne_annee(self):
        """Chaque acquisition compte pour l'année de son échéance."""
        services.crediter_acquisitions(self.salarie, date(2027, 3, 15))

        self.assertEqual(services.solde(self.salarie, 2026), Decimal("7.5"))
        self.assertEqual(services.solde(self.salarie, 2027), Decimal("7.5"))

    def test_sans_date_d_embauche_aucun_credit(self):
        sans_embauche = User.objects.create_user(
            "sans", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)
        self.assertEqual(
            services.crediter_acquisitions(sans_embauche, date(2027, 1, 1)), 0)

    def test_traitement_de_masse_ignore_les_inactifs(self):
        parti = User.objects.create_user(
            "parti", password="x", role=User.Role.EMPLOYE, filiale=self.kapi,
            date_embauche=date(2026, 1, 1), is_active=False)

        services.crediter_toutes_les_acquisitions(date(2026, 12, 15))

        self.assertEqual(services.solde(parti, 2026), Decimal("0"))

    def test_appel_via_celery(self):
        resultat = tache_acquisition.delay()
        self.assertTrue(resultat.successful())


class DisponibiliteTests(BaseSoldes, TestCase):
    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.salarie, date(2027, 9, 15))

    def test_demande_en_attente_reserve_les_jours(self):
        """
        Sans réserve, deux demandes soumises coup sur coup verraient
        chacune un solde intact et pourraient être validées toutes les deux.
        """
        avant = services.solde_disponible(self.salarie, 2027)

        DemandeConge.objects.create(
            utilisateur=self.salarie, type_conge=TypeConge.ANNUEL,
            date_debut=date(2027, 7, 5), date_fin=date(2027, 7, 9),
            jours_ouvres=5)

        self.assertEqual(
            services.solde_disponible(self.salarie, 2027), avant - 5)
        self.assertEqual(services.solde(self.salarie, 2027), avant)

    def test_conge_maladie_ne_reserve_rien(self):
        avant = services.solde_disponible(self.salarie, 2027)

        DemandeConge.objects.create(
            utilisateur=self.salarie, type_conge=TypeConge.MALADIE,
            date_debut=date(2027, 7, 5), date_fin=date(2027, 7, 9),
            jours_ouvres=5)

        self.assertEqual(services.solde_disponible(self.salarie, 2027), avant)

    def test_situation_complete(self):
        situation = services.situation(self.salarie, 2027)
        self.assertEqual(situation["annee"], 2027)
        self.assertEqual(situation["acquis"], Decimal("22.5"))  # janv. à sept.
        self.assertEqual(situation["pris"], Decimal("0"))


class ConsommationTests(BaseSoldes, TestCase):
    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.salarie, date(2027, 9, 15))
        self.demande = DemandeConge.objects.create(
            utilisateur=self.salarie, type_conge=TypeConge.ANNUEL,
            date_debut=date(2027, 7, 5), date_fin=date(2027, 7, 9),
            jours_ouvres=5, statut=DemandeConge.Statut.VALIDEE)

    def test_consommation_debite(self):
        avant = services.solde(self.salarie, 2027)
        services.consommer(self.demande)
        self.assertEqual(services.solde(self.salarie, 2027), avant - 5)

    def test_consommation_idempotente(self):
        services.consommer(self.demande)
        services.consommer(self.demande)
        self.assertEqual(
            MouvementConge.objects.filter(
                demande=self.demande,
                type_mouvement=MouvementConge.TypeMouvement.CONSOMMATION,
            ).count(),
            1,
        )

    def test_maladie_ne_debite_pas(self):
        maladie = DemandeConge.objects.create(
            utilisateur=self.salarie, type_conge=TypeConge.MALADIE,
            date_debut=date(2027, 8, 2), date_fin=date(2027, 8, 6),
            jours_ouvres=5, statut=DemandeConge.Statut.VALIDEE)

        avant = services.solde(self.salarie, 2027)
        self.assertIsNone(services.consommer(maladie))
        self.assertEqual(services.solde(self.salarie, 2027), avant)

    def test_restitution_recredite(self):
        avant = services.solde(self.salarie, 2027)
        services.consommer(self.demande)
        services.restituer(self.demande)
        self.assertEqual(services.solde(self.salarie, 2027), avant)

    def test_restitution_sans_consommation_ne_rend_rien(self):
        """Une demande annulée avant validation n'a rien consommé."""
        self.assertIsNone(services.restituer(self.demande))

    def test_restitution_idempotente(self):
        services.consommer(self.demande)
        services.restituer(self.demande)
        services.restituer(self.demande)
        self.assertEqual(
            MouvementConge.objects.filter(
                demande=self.demande,
                type_mouvement=MouvementConge.TypeMouvement.RESTITUTION,
            ).count(),
            1,
        )


class ExpirationTests(BaseSoldes, TestCase):
    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.salarie, date(2026, 12, 20))

    def test_solde_perdu_au_31_decembre(self):
        perdu = services.expirer_solde(self.salarie, 2026)

        self.assertEqual(perdu, Decimal("7.5"))
        self.assertEqual(services.solde(self.salarie, 2026), Decimal("0"))

    def test_perte_tracee_au_registre(self):
        """Le salarié doit pouvoir voir combien il a perdu, et quand."""
        services.expirer_solde(self.salarie, 2026)

        mouvement = MouvementConge.objects.get(
            utilisateur=self.salarie,
            type_mouvement=MouvementConge.TypeMouvement.EXPIRATION)
        self.assertEqual(mouvement.jours, Decimal("-7.5"))
        self.assertEqual(mouvement.date_effet, date(2026, 12, 31))

    def test_idempotente(self):
        services.expirer_solde(self.salarie, 2026)
        self.assertEqual(services.expirer_solde(self.salarie, 2026), Decimal("0"))
        self.assertEqual(
            MouvementConge.objects.filter(
                type_mouvement=MouvementConge.TypeMouvement.EXPIRATION).count(),
            1,
        )

    def test_n_affecte_pas_les_autres_annees(self):
        services.crediter_acquisitions(self.salarie, date(2027, 3, 15))
        services.expirer_solde(self.salarie, 2026)

        self.assertEqual(services.solde(self.salarie, 2026), Decimal("0"))
        self.assertEqual(services.solde(self.salarie, 2027), Decimal("7.5"))

    def test_solde_nul_n_ecrit_rien(self):
        vide = User.objects.create_user(
            "vide", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)
        self.assertEqual(services.expirer_solde(vide, 2026), Decimal("0"))
        self.assertFalse(
            MouvementConge.objects.filter(utilisateur=vide).exists())


class GardeFouExpirationTests(BaseSoldes, TestCase):
    """
    L'expiration est destructrice : elle vérifie elle-même la date et
    l'existence d'un plafond, plutôt que de faire confiance à son
    ordonnanceur.

    Ces tests décrivent le comportement SI le plafond légal de report était
    activé (`CONGES_REPORT_MAX_ANNEES`). En fonctionnement courant il ne
    l'est pas, et rien n'expire — voir `TacheExpirationInactiveTests`.
    """

    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.salarie, date(2026, 12, 20))

    @override_settings(CONGES_REPORT_MAX_ANNEES=0)
    def test_refuse_d_agir_hors_du_31_decembre(self):
        from unittest import mock
        from applications.conges.tasks import expirer_soldes

        with mock.patch(
            "applications.conges.tasks.timezone.localdate",
            return_value=date(2026, 6, 15),
        ):
            resultat = expirer_soldes()

        self.assertIn("31/12", resultat)
        self.assertEqual(services.solde(self.salarie), Decimal("7.5"))

    @override_settings(CONGES_REPORT_MAX_ANNEES=0)
    def test_agit_le_31_decembre_si_un_plafond_est_configure(self):
        from unittest import mock
        from applications.conges.tasks import expirer_soldes

        with mock.patch(
            "applications.conges.tasks.timezone.localdate",
            return_value=date(2026, 12, 31),
        ):
            expirer_soldes()

        self.assertEqual(services.solde(self.salarie), Decimal("0"))

    @override_settings(CONGES_REPORT_MAX_ANNEES=2)
    def test_le_plafond_determine_l_annee_purgee(self):
        """Avec un report de deux ans, on purge l'année N-2, pas l'année N."""
        from unittest import mock
        from applications.conges.tasks import expirer_soldes

        services.crediter_acquisitions(self.salarie, date(2028, 12, 20))

        with mock.patch(
            "applications.conges.tasks.timezone.localdate",
            return_value=date(2028, 12, 31),
        ):
            expirer_soldes()

        self.assertEqual(services.solde(self.salarie, 2026), Decimal("0"))
        self.assertGreater(services.solde(self.salarie, 2028), Decimal("0"))

    def test_forcage_manuel_possible(self):
        from applications.conges.tasks import expirer_soldes

        expirer_soldes(annee=2026, forcer=True)

        self.assertEqual(services.solde(self.salarie), Decimal("0"))


class CumulSansLimiteTests(BaseSoldes, TestCase):
    """
    Les congés non pris se reportent sans limite de temps : ils ne sont
    jamais perdus en fin d'année (décision OSEOR, plus favorable que le
    report légal de deux ans du Code du travail togolais).
    """

    def setUp(self):
        self.creer_donnees()

    def test_solde_cumule_sur_plusieurs_annees(self):
        services.crediter_acquisitions(self.salarie, date(2028, 9, 15))

        # 24 échéances d'octobre 2026 à septembre 2028.
        self.assertEqual(services.solde(self.salarie), Decimal("60"))

    def test_solde_par_annee_reste_consultable(self):
        """Le détail annuel sert à expliquer un compteur, pas à le cloisonner."""
        services.crediter_acquisitions(self.salarie, date(2027, 12, 15))

        self.assertEqual(services.solde(self.salarie, 2026), Decimal("7.5"))
        self.assertEqual(services.solde(self.salarie, 2027), Decimal("30"))
        self.assertEqual(services.solde(self.salarie), Decimal("37.5"))

    def test_situation_expose_cumul_et_annee(self):
        services.crediter_acquisitions(self.salarie, date(2027, 12, 15))

        situation = services.situation(self.salarie, 2027)

        self.assertEqual(situation["acquis_total"], Decimal("37.5"))
        self.assertEqual(situation["acquis"], Decimal("30"))
        self.assertEqual(situation["solde"], Decimal("37.5"))

    def test_reserve_cumulative(self):
        """Une demande pour l'an prochain mobilise des jours dès maintenant."""
        services.crediter_acquisitions(self.salarie, date(2027, 12, 15))

        DemandeConge.objects.create(
            utilisateur=self.salarie, type_conge=TypeConge.ANNUEL,
            date_debut=date(2028, 2, 7), date_fin=date(2028, 2, 11),
            jours_ouvres=5)

        self.assertEqual(
            services.solde_disponible(self.salarie), Decimal("32.5"))


class TacheExpirationInactiveTests(BaseSoldes, TestCase):
    """
    La tâche d'expiration existe encore, pour le jour où le plafond légal
    de report serait appliqué — mais elle ne doit rien faire tant qu'aucun
    plafond n'est configuré.
    """

    def setUp(self):
        self.creer_donnees()
        services.crediter_acquisitions(self.salarie, date(2026, 12, 20))

    def test_sans_plafond_configure_ne_fait_rien(self):
        from applications.conges.tasks import expirer_soldes

        resultat = expirer_soldes()

        self.assertIn("cumulent sans limite", resultat)
        self.assertEqual(services.solde(self.salarie), Decimal("7.5"))

    def test_absente_de_la_planification(self):
        """Aucune tâche planifiée ne doit purger un solde."""
        from applications.planification.registre import collecter_taches

        taches = [t["tache"] for t in collecter_taches()]

        self.assertNotIn("conges.expirer_soldes", taches)

    def test_forcage_manuel_reste_possible(self):
        from applications.conges.tasks import expirer_soldes

        expirer_soldes(annee=2026, forcer=True)

        self.assertEqual(services.solde(self.salarie), Decimal("0"))
