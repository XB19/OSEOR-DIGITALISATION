"""
Registre des tâches planifiées du projet.

Chaque application déclare ses propres traitements périodiques dans son
module `tasks.py`, via une constante `TACHES_PLANIFIEES`. Le registre les
collecte : personne n'a à tenir une liste centrale à jour, et une
application qui part emporte ses horaires avec elle.

Format d'une déclaration :

    TACHES_PLANIFIEES = [
        {
            "nom": "Relance des documents en attente de visa",
            "tache": "documents.rappeler_documents_en_attente",
            "crontab": {"minute": "0", "hour": "8", "day_of_week": "1-5"},
            "kwargs": {"seuil_jours": 3},
            "description": "Renotifie les visas dormants.",
        },
    ]
"""

from importlib import import_module

from django.apps import apps

CHAMPS_REQUIS = ("nom", "tache", "crontab")


def collecter_taches():
    """
    Parcourt les applications installées et rassemble leurs déclarations.

    Renvoie la liste des tâches, triée par nom pour que la sortie de la
    commande de seed reste stable d'une exécution à l'autre.
    """
    declarations = []

    for config in apps.get_app_configs():
        try:
            module = import_module(f"{config.name}.tasks")
        except ModuleNotFoundError:
            # La plupart des applications n'ont pas de tâches : cas normal.
            continue

        for declaration in getattr(module, "TACHES_PLANIFIEES", []):
            declarations.append((config.name, declaration))

    return valider(declarations)


def valider(declarations):
    """
    Contrôle les déclarations collectées et les renvoie triées par nom.

    `declarations` est une liste de couples (nom d'application, déclaration).
    Les deux erreurs vérifiées ici sont silencieuses autrement : un champ
    manquant ne se voit qu'au moment où beat tente de lancer la tâche, et
    deux tâches homonymes s'écrasent l'une l'autre en base — `name` est la
    clé d'unicité de PeriodicTask.
    """
    resultat, vus, doublons = [], set(), set()

    for origine, declaration in declarations:
        manquants = [c for c in CHAMPS_REQUIS if c not in declaration]
        if manquants:
            raise ValueError(
                f"{origine}.tasks.TACHES_PLANIFIEES : champ(s) "
                f"{', '.join(manquants)} manquant(s) dans {declaration!r}"
            )

        nom = declaration["nom"]
        if nom in vus:
            doublons.add(nom)
        vus.add(nom)
        resultat.append(declaration)

    if doublons:
        raise ValueError(
            "Deux tâches planifiées portent le même nom, ce qui les ferait "
            f"s'écraser en base : {', '.join(sorted(doublons))}"
        )

    return sorted(resultat, key=lambda d: d["nom"])
