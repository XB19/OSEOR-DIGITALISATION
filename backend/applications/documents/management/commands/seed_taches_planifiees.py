"""
Enregistre les tâches planifiées par défaut dans django-celery-beat.

Les horaires sont ensuite modifiables depuis l'admin Django
(« Periodic tasks »), sans redéploiement : c'est tout l'intérêt du
DatabaseScheduler. Cette commande ne pose que les valeurs initiales.

Ré-exécutable : met à jour l'existant plutôt que de le dupliquer, et ne
réécrit jamais un horaire déjà ajusté à la main.

Usage : python manage.py seed_taches_planifiees
"""

import json

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


# (nom, tâche, horaire crontab, arguments)
TACHES = [
    {
        "nom": "Relance des documents en attente de visa",
        "tache": "documents.rappeler_documents_en_attente",
        "crontab": {"minute": "0", "hour": "8", "day_of_week": "1-5"},
        "kwargs": {"seuil_jours": 3},
        "description": (
            "Chaque matin ouvré à 8h, renotifie les visas dormants depuis "
            "plus de 3 jours."
        ),
    },
]


class Command(BaseCommand):
    help = "Enregistre les tâches planifiées par défaut (django-celery-beat)."

    def handle(self, *args, **options):
        for definition in TACHES:
            horaire, _ = CrontabSchedule.objects.get_or_create(
                **definition["crontab"],
                defaults={"day_of_month": "*", "month_of_year": "*"},
            )

            tache, cree = PeriodicTask.objects.get_or_create(
                name=definition["nom"],
                defaults={
                    "task": definition["tache"],
                    "crontab": horaire,
                    "kwargs": json.dumps(definition["kwargs"]),
                    "description": definition["description"],
                },
            )

            if cree:
                self.stdout.write(self.style.SUCCESS(f"Créée : {tache.name}"))
                continue

            # La tâche existe : on remet à jour ce qui vient du code, mais on
            # laisse l'horaire tel que l'administrateur l'a réglé.
            tache.task = definition["tache"]
            tache.description = definition["description"]
            tache.save(update_fields=["task", "description"])
            self.stdout.write(f"Inchangée (horaire préservé) : {tache.name}")
