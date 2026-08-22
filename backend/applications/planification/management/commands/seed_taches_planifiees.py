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


class Command(BaseCommand):
    help = "Enregistre les tâches planifiées déclarées par les applications."

    def handle(self, *args, **options):
        taches = collecter_taches()

        if not taches:
            self.stdout.write("Aucune tâche planifiée déclarée.")
            return

        for definition in taches:
            self._enregistrer(definition)

    def _enregistrer(self, definition):
        horaire, _ = CrontabSchedule.objects.get_or_create(
            **definition["crontab"],
            defaults={"day_of_month": "*", "month_of_year": "*"},
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
        # laisse l'horaire tel que l'administrateur l'a réglé.
        tache.task = definition["tache"]
        tache.description = definition.get("description", "")
        tache.save(update_fields=["task", "description"])
        self.stdout.write(f"Inchangée (horaire préservé) : {tache.name}")
