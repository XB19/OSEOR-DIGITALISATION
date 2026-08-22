"""
Enregistre les jours fériés togolais d'une ou plusieurs années.

Ne pose que les dates fixes et celles déduites de Pâques. L'Aïd el-Fitr et
l'Aïd el-Adha suivent le calendrier lunaire et sont fixés chaque année par
décret : ils se saisissent depuis l'admin Django (« Jours fériés »).

Ré-exécutable : ne recrée pas une date déjà présente, et ne touche pas aux
jours fériés saisis à la main.

Usage :
    python manage.py seed_jours_feries              # année courante et suivante
    python manage.py seed_jours_feries --annee 2027
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from applications.conges.calendrier import feries_calcules
from applications.conges.models import JourFerie


class Command(BaseCommand):
    help = "Enregistre les jours fériés togolais (hors fêtes musulmanes)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--annee", type=int, action="append", dest="annees",
            help="Année à traiter (répétable). Défaut : année courante et suivante.",
        )

    def handle(self, *args, **options):
        annees = options.get("annees")
        if not annees:
            courante = timezone.now().year
            annees = [courante, courante + 1]

        crees = 0
        for annee in annees:
            for jour, nom in feries_calcules(annee):
                _, cree = JourFerie.objects.get_or_create(
                    date=jour, filiale=None, defaults={"nom": nom},
                )
                if cree:
                    crees += 1
                    self.stdout.write(f"  {jour:%d/%m/%Y} — {nom}")

        self.stdout.write(self.style.SUCCESS(
            f"{crees} jour(s) férié(s) ajouté(s) pour {', '.join(map(str, annees))}."
        ))
        self.stdout.write(self.style.WARNING(
            "Aïd el-Fitr et Aïd el-Adha ne sont pas inclus (calendrier "
            "lunaire) : à saisir dans l'admin, rubrique « Jours fériés »."
        ))
