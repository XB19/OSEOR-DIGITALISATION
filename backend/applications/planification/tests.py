"""
Registre des tâches planifiées : collecte auprès des applications et
contrôles qui évitent deux pannes silencieuses — une tâche mal déclarée ne
se voit qu'au moment où beat tente de la lancer, et deux tâches homonymes
s'écrasent en base sans prévenir.
"""

from django.test import TestCase

from applications.planification.registre import collecter_taches, valider


TACHE = {
    "nom": "Tâche A",
    "tache": "module.tache_a",
    "crontab": {"minute": "0", "hour": "6"},
}


class ValidationTests(TestCase):
    def test_trie_par_nom(self):
        b = dict(TACHE, nom="Tâche B")
        resultat = valider([("app_x", b), ("app_y", TACHE)])
        self.assertEqual([d["nom"] for d in resultat], ["Tâche A", "Tâche B"])

    def test_champ_manquant_signale_l_application_fautive(self):
        incomplete = {"nom": "Sans tâche", "crontab": {}}
        with self.assertRaises(ValueError) as erreur:
            valider([("applications.stocks", incomplete)])
        self.assertIn("applications.stocks", str(erreur.exception))
        self.assertIn("tache", str(erreur.exception))

    def test_noms_en_double_refuses(self):
        """`name` est la clé d'unicité de PeriodicTask : deux homonymes
        s'écraseraient l'un l'autre."""
        with self.assertRaises(ValueError) as erreur:
            valider([("app_x", TACHE), ("app_y", dict(TACHE))])
        self.assertIn("Tâche A", str(erreur.exception))

    def test_liste_vide_acceptee(self):
        self.assertEqual(valider([]), [])


class CollecteTests(TestCase):
    def test_trouve_les_taches_declarees_par_les_applications(self):
        noms = [d["nom"] for d in collecter_taches()]
        self.assertIn("Relance des documents en attente de visa", noms)

    def test_toutes_les_declarations_sont_completes(self):
        """Garde-fou permanent : une déclaration ajoutée sans ses champs
        obligatoires fait échouer la suite, pas la production."""
        for declaration in collecter_taches():
            self.assertIn("nom", declaration)
            self.assertIn("tache", declaration)
            self.assertIn("crontab", declaration)
