"""
Enregistre dans django-celery-beat les tâches planifiées déclarées par les
applications (voir `applications/planification/registre.py`).

Les horaires sont ensuite modifiables depuis l'admin Django
(« Periodic tasks ») sans redéploiement : cette commande ne pose que les
valeurs initiales.

Ré-exécutable : met à jour l'existant plutôt que de le dupliquer, et ne
réécrit jamais un horaire déjà ajusté à la main.

Usage : python manage.py seed_taches_planifiees
"""

import json

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from applications.planification.registre import collecter_taches

#: Champs d'un crontab, tous à « * » par défaut.
#:
#: Ils sont TOUS passés en critère de recherche, jamais via `defaults` :
#: `get_or_create` applique les `defaults` PAR-DESSUS les critères à la
#: création, si bien qu'un `defaults={"day_of_month": "*"}` écrasait
#: silencieusement un `day_of_month="31"` explicite. L'expiration des
#: congés, seule tâche à préciser un jour et un mois, se retrouvait
#: programmée toutes les nuits — et vidait le solde de tout le personnel
#: chaque soir.
CRONTAB_COMPLET = {
    "minute": "*",
    "hour": "*",
    "day_of_month": "*",
    "month_of_year": "*",
    "day_of_week": "*",
}


class Command(BaseCommand):
    help = "Enregistre les tâches planifiées déclarées par les applications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reinitialiser-horaires", action="store_true",
            help="Remet les horaires aux valeurs déclarées dans le code, en "
                 "écrasant les réglages faits depuis l'admin. À n'utiliser "
                 "que pour réparer une planification erronée.",
        )

    def handle(self, *args, **options):
        taches = collecter_taches()

        if not taches:
            self.stdout.write("Aucune tâche planifiée déclarée.")
            return

        for definition in taches:
            self._enregistrer(definition, options["reinitialiser_horaires"])

        self._signaler_orphelines(taches)

    def _signaler_orphelines(self, taches):
        """
        Signale les tâches encore planifiées en base qu'aucune application
        ne déclare plus.

        Elles subsistent parce que le seed ne supprime jamais rien — il ne
        peut pas distinguer une tâche retirée du code d'une tâche créée à la
        main depuis l'admin. Les signaler laisse l'arbitrage à l'exploitant
        plutôt que d'effacer une planification qu'il aurait voulue.
        """
        declarees = {d["nom"] for d in taches}

        orphelines = (
            PeriodicTask.objects
            .exclude(name__in=declarees)
            .exclude(name__startswith="celery.")
        )

        for tache in orphelines:
            self.stdout.write(self.style.WARNING(
                f"Orpheline : « {tache.name} » ({tache.task}) est planifiée en "
                f"base mais plus déclarée dans le code. À désactiver depuis "
                f"l'admin si elle n'a plus lieu d'être."
            ))

    def _enregistrer(self, definition, reinitialiser=False):
        horaire, _ = CrontabSchedule.objects.get_or_create(
            **{**CRONTAB_COMPLET, **definition["crontab"]},
        )

        tache, cree = PeriodicTask.objects.get_or_create(
            name=definition["nom"],
            defaults={
                "task": definition["tache"],
                "crontab": horaire,
                "kwargs": json.dumps(definition.get("kwargs", {})),
                "description": definition.get("description", ""),
            },
        )

        if cree:
            self.stdout.write(self.style.SUCCESS(f"Créée : {tache.name}"))
            return

        # La tâche existe : on remet à jour ce qui vient du code, mais on
        # laisse l'horaire tel que l'administrateur l'a réglé — sauf demande
        # explicite de réinitialisation, seul moyen de réparer une
        # planification déjà enregistrée de travers.
        tache.task = definition["tache"]
        tache.description = definition.get("description", "")
        champs = ["task", "description"]

        if reinitialiser and tache.crontab_id != horaire.pk:
            ancien = tache.crontab
            tache.crontab = horaire
            champs.append("crontab")
            tache.save(update_fields=champs)
            self.stdout.write(self.style.WARNING(
                f"Horaire réinitialisé : {tache.name} ({ancien} -> {horaire})"))
            return

        tache.save(update_fields=champs)
        self.stdout.write(f"Inchangée (horaire préservé) : {tache.name}")
