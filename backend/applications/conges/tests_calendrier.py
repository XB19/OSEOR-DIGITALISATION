"""
Calendrier ouvré : Pâques, jours fériés togolais et décompte des jours
ouvrés.

C'est l'arithmétique qui décide combien de jours un salarié perd sur son
solde. Une erreur d'un jour se voit sur une fiche de paie, d'où une
couverture serrée — bornes incluses, week-ends, fériés, intervalles
dégénérés.
"""

from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from applications.conges.calendrier import (
    compter_jours_ouvres, est_ouvre, feries_calcules, jours_ouvres, paques,
)
from applications.conges.models import JourFerie
from applications.filiales.models import Filiale


class PaquesTests(TestCase):
    """Dates de référence connues, pour verrouiller l'algorithme grégorien."""

    def test_dates_connues(self):
        attendu = {
            2024: date(2024, 3, 31),
            2025: date(2025, 4, 20),
            2026: date(2026, 4, 5),
            2027: date(2027, 3, 28),
            2028: date(2028, 4, 16),
        }
        for annee, jour in attendu.items():
            with self.subTest(annee=annee):
                self.assertEqual(paques(annee), jour)

    def test_toujours_un_dimanche(self):
        for annee in range(2020, 2041):
            with self.subTest(annee=annee):
                self.assertEqual(paques(annee).weekday(), 6)


class FeriesCalculesTests(TestCase):
    def test_contient_les_dates_fixes(self):
        dates = dict(feries_calcules(2027))
        self.assertEqual(dates[date(2027, 1, 1)], "Jour de l'An")
        self.assertEqual(dates[date(2027, 4, 27)], "Fête de l'Indépendance")
        self.assertEqual(dates[date(2027, 12, 25)], "Noël")

    def test_feries_mobiles_deduits_de_paques(self):
        dates = dict(feries_calcules(2027))
        # Pâques 2027 : 28 mars.
        self.assertEqual(dates[date(2027, 3, 29)], "Lundi de Pâques")
        self.assertEqual(dates[date(2027, 5, 6)], "Ascension")
        self.assertEqual(dates[date(2027, 5, 17)], "Lundi de Pentecôte")

    def test_trie_par_date(self):
        dates = [jour for jour, _ in feries_calcules(2027)]
        self.assertEqual(dates, sorted(dates))

    def test_fetes_musulmanes_absentes(self):
        """
        Calendrier lunaire : elles sont saisies à la main. Ce test fige
        l'intention — si quelqu'un les ajoute en dur un jour, il devra
        d'abord expliquer pourquoi ici.
        """
        noms = [nom for _, nom in feries_calcules(2027)]
        self.assertNotIn("Aïd el-Fitr", noms)
        self.assertNotIn("Aïd el-Adha", noms)


class EstOuvreTests(TestCase):
    def test_jours_de_semaine(self):
        # 2027-03-15 est un lundi.
        self.assertTrue(est_ouvre(date(2027, 3, 15)))
        self.assertTrue(est_ouvre(date(2027, 3, 19)))  # vendredi

    def test_week_end(self):
        self.assertFalse(est_ouvre(date(2027, 3, 20)))  # samedi
        self.assertFalse(est_ouvre(date(2027, 3, 21)))  # dimanche

    def test_ferie_en_semaine(self):
        self.assertFalse(
            est_ouvre(date(2027, 3, 15), feries={date(2027, 3, 15)}))


class JoursOuvresTests(TestCase):
    def setUp(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")

    def test_semaine_complete(self):
        """Lundi 15 au vendredi 19 mars 2027 : 5 jours."""
        self.assertEqual(
            compter_jours_ouvres(date(2027, 3, 15), date(2027, 3, 19)), 5)

    def test_bornes_incluses(self):
        """Un seul jour, début = fin, doit compter pour 1."""
        self.assertEqual(
            compter_jours_ouvres(date(2027, 3, 15), date(2027, 3, 15)), 1)

    def test_week_end_exclu(self):
        """Lundi au lundi suivant : 6 jours ouvrés, pas 8."""
        self.assertEqual(
            compter_jours_ouvres(date(2027, 3, 15), date(2027, 3, 22)), 6)

    def test_un_seul_jour_de_week_end(self):
        self.assertEqual(
            compter_jours_ouvres(date(2027, 3, 20), date(2027, 3, 21)), 0)

    def test_ferie_du_groupe_decompte(self):
        JourFerie.objects.create(
            date=date(2027, 3, 17), nom="Férié test", filiale=None)
        self.assertEqual(
            compter_jours_ouvres(date(2027, 3, 15), date(2027, 3, 19)), 4)

    def test_ferie_propre_a_une_filiale(self):
        JourFerie.objects.create(
            date=date(2027, 3, 17), nom="Fête KAPI", filiale=self.kapi)

        self.assertEqual(
            compter_jours_ouvres(date(2027, 3, 15), date(2027, 3, 19), self.kapi), 4)
        self.assertEqual(
            compter_jours_ouvres(date(2027, 3, 15), date(2027, 3, 19), self.oseor), 5)

    def test_ferie_tombant_un_dimanche_ne_compte_pas_double(self):
        JourFerie.objects.create(
            date=date(2027, 3, 21), nom="Férié dominical", filiale=None)
        self.assertEqual(
            compter_jours_ouvres(date(2027, 3, 15), date(2027, 3, 21)), 5)

    def test_intervalle_inverse_renvoie_zero(self):
        """Un décompte négatif serait bien plus dangereux qu'un zéro."""
        self.assertEqual(
            compter_jours_ouvres(date(2027, 3, 19), date(2027, 3, 15)), 0)
        self.assertEqual(jours_ouvres(date(2027, 3, 19), date(2027, 3, 15)), [])

    def test_liste_des_jours(self):
        self.assertEqual(
            jours_ouvres(date(2027, 3, 15), date(2027, 3, 17)),
            [date(2027, 3, 15), date(2027, 3, 16), date(2027, 3, 17)],
        )


class SeedJoursFeriesTests(TestCase):
    def test_cree_les_feries_d_une_annee(self):
        call_command("seed_jours_feries", annee=[2027], stdout=StringIO())

        self.assertEqual(JourFerie.objects.filter(date__year=2027).count(), 11)
        self.assertTrue(
            JourFerie.objects.filter(date=date(2027, 4, 27)).exists())

    def test_reexecutable_sans_doublon(self):
        call_command("seed_jours_feries", annee=[2027], stdout=StringIO())
        call_command("seed_jours_feries", annee=[2027], stdout=StringIO())

        self.assertEqual(JourFerie.objects.filter(date__year=2027).count(), 11)

    def test_ne_touche_pas_aux_saisies_manuelles(self):
        """Les fêtes musulmanes saisies à la main doivent survivre au seed."""
        JourFerie.objects.create(
            date=date(2027, 3, 9), nom="Aïd el-Fitr", filiale=None)

        call_command("seed_jours_feries", annee=[2027], stdout=StringIO())

        self.assertTrue(
            JourFerie.objects.filter(nom="Aïd el-Fitr").exists())

    def test_plusieurs_annees(self):
        call_command("seed_jours_feries", annee=[2027, 2028], stdout=StringIO())
        self.assertTrue(JourFerie.objects.filter(date__year=2027).exists())
        self.assertTrue(JourFerie.objects.filter(date__year=2028).exists())
