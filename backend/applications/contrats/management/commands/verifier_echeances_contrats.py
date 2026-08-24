"""
Vérifie l'échéance de tous les contrats actifs et envoie les alertes
d'expiration (30/15/7/3/1 jours avant échéance), ainsi que la notification de
passage au statut « Expiré ». Idempotent — ré-exécutable sans doublons.

À programmer en tâche planifiée quotidienne (ex. Planificateur de tâches
Windows, ou cron sur un hôte Linux) :

    python manage.py verifier_echeances_contrats

Le même contrôle tourne aussi en best-effort à chaque consultation de la
liste des contrats dans l'application (cf. ContratViewSet.list) — cette
commande garantit qu'il s'exécute même si personne ne consulte la page un
jour donné.
"""

from django.core.management.base import BaseCommand

from applications.contrats.services import verifier_echeances_et_alerter


class Command(BaseCommand):
    help = "Vérifie les échéances de contrats et envoie les alertes d'expiration."

    def handle(self, *args, **options):
        verifier_echeances_et_alerter()
        self.stdout.write(self.style.SUCCESS("Vérification des échéances de contrats terminée."))
