"""
Tâches planifiées : relance des visas dormants, et enregistrement des
horaires dans django-celery-beat.

En test, Celery s'exécute en mode « eager » (synchrone, sans broker) :
`.delay()` déclenche la tâche immédiatement dans le processus courant, ce
qui rend la chaîne complète vérifiable sans Redis ni worker.
"""

import json
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from applications.documents.models import Document
from applications.documents.services import rappeler_documents_en_attente
from applications.documents.tasks import (
    rappeler_documents_en_attente as tache_relance,
)
from applications.documents.tests import BaseDocuments
from applications.notifications.models import Notification


class RelanceDesVisasTests(BaseDocuments, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.document = self.creer_document()

    def _vieillir(self, document, jours):
        """`date_modification` est auto_now : seul un UPDATE direct la fixe."""
        Document.objects.filter(pk=document.pk).update(
            date_modification=timezone.now() - timedelta(days=jours))

    def test_document_dormant_relance_le_role_attendu(self):
        self._vieillir(self.document, 5)

        self.assertEqual(rappeler_documents_en_attente(seuil_jours=3), 1)

        destinataires = set(
            Notification.objects.values_list("utilisateur_id", flat=True))
        self.assertEqual(destinataires, {self.comptable.pk})

    def test_document_recent_ignore(self):
        self._vieillir(self.document, 1)
        self.assertEqual(rappeler_documents_en_attente(seuil_jours=3), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_document_cloture_ignore(self):
        self.document.statut = Document.Statut.VALIDE
        self.document.save()
        self._vieillir(self.document, 10)

        self.assertEqual(rappeler_documents_en_attente(seuil_jours=3), 0)

    def test_document_sans_chaine_de_visas_ignore(self):
        document = self.creer_document(
            demandeur=self.employe_oseor, filiale=self.oseor)
        self._vieillir(document, 10)

        self.assertEqual(rappeler_documents_en_attente(seuil_jours=3), 0)

    def test_idempotente_sur_l_etat_des_documents(self):
        """
        ACKS_LATE fait rejouer une tâche interrompue : relancer ne doit
        rien changer aux documents, seulement renotifier.
        """
        self._vieillir(self.document, 5)
        avant = Document.objects.get(pk=self.document.pk)

        rappeler_documents_en_attente(seuil_jours=3)
        rappeler_documents_en_attente(seuil_jours=3)

        apres = Document.objects.get(pk=self.document.pk)
        self.assertEqual(apres.statut, avant.statut)
        self.assertEqual(apres.etape_visa_courante, avant.etape_visa_courante)
        self.assertEqual(apres.historique_visas, avant.historique_visas)

    def test_appel_via_celery(self):
        """La tâche est bien enregistrée et appelable par le worker."""
        self._vieillir(self.document, 5)

        resultat = tache_relance.delay(seuil_jours=3)

        self.assertTrue(resultat.successful())
        self.assertEqual(resultat.get(), 1)


class SeedTachesPlanifieesTests(TestCase):
    def test_cree_la_tache_periodique(self):
        call_command("seed_taches_planifiees", stdout=StringIO())

        tache = PeriodicTask.objects.get(
            name="Relance des documents en attente de visa")
        self.assertEqual(tache.task, "documents.rappeler_documents_en_attente")
        self.assertEqual(json.loads(tache.kwargs), {"seuil_jours": 3})
        self.assertEqual(tache.crontab.hour, "8")

    def test_reexecutable_sans_doublon(self):
        call_command("seed_taches_planifiees", stdout=StringIO())
        call_command("seed_taches_planifiees", stdout=StringIO())

        self.assertEqual(
            PeriodicTask.objects.filter(
                name="Relance des documents en attente de visa").count(),
            1,
        )

    def test_horaire_annuel_conserve_jour_et_mois(self):
        """
        Regression : `get_or_create` applique ses `defaults` PAR-DESSUS les
        critères de recherche. Un `defaults={"day_of_month": "*"}` écrasait
        le 31/12 de l'expiration des congés, qui se retrouvait planifiée
        toutes les nuits — et vidait le solde de tout le personnel chaque
        soir.
        """
        call_command("seed_taches_planifiees", stdout=StringIO())

        tache = PeriodicTask.objects.get(name="Expiration des soldes de congés")

        self.assertEqual(tache.crontab.day_of_month, "31")
        self.assertEqual(tache.crontab.month_of_year, "12")
        self.assertEqual(tache.crontab.hour, "23")

    def test_chaque_tache_a_l_horaire_declare(self):
        """Aucun champ de crontab déclaré ne doit se perdre au passage."""
        from applications.planification.registre import collecter_taches

        call_command("seed_taches_planifiees", stdout=StringIO())

        for declaration in collecter_taches():
            with self.subTest(tache=declaration["nom"]):
                horaire = PeriodicTask.objects.get(
                    name=declaration["nom"]).crontab
                for champ, valeur in declaration["crontab"].items():
                    self.assertEqual(getattr(horaire, champ), valeur)

    def test_preserve_un_horaire_ajuste_a_la_main(self):
        """
        Tout l'intérêt du DatabaseScheduler : un administrateur décale le
        traitement depuis l'admin, et un redéploiement ne le réécrase pas.
        """
        call_command("seed_taches_planifiees", stdout=StringIO())
        tache = PeriodicTask.objects.get(
            name="Relance des documents en attente de visa")
        horaire = tache.crontab
        horaire.hour = "17"
        horaire.save()

        call_command("seed_taches_planifiees", stdout=StringIO())

        tache.refresh_from_db()
        self.assertEqual(tache.crontab.hour, "17")


class ReinitialisationHorairesTests(TestCase):
    """
    Le seed préserve les horaires réglés depuis l'admin — c'est voulu, mais
    cela empêche aussi de réparer une planification enregistrée de travers.
    D'où l'option explicite.
    """

    NOM = "Expiration des soldes de congés"

    def _fausser_horaire(self):
        call_command("seed_taches_planifiees", stdout=StringIO())
        tache = PeriodicTask.objects.get(name=self.NOM)
        faux = CrontabSchedule.objects.create(
            minute="30", hour="23", day_of_month="*", month_of_year="*",
            day_of_week="*")
        tache.crontab = faux
        tache.save(update_fields=["crontab"])
        return tache

    def test_sans_option_l_horaire_errone_persiste(self):
        self._fausser_horaire()

        call_command("seed_taches_planifiees", stdout=StringIO())

        tache = PeriodicTask.objects.get(name=self.NOM)
        self.assertEqual(tache.crontab.day_of_month, "*")

    def test_option_remet_l_horaire_declare(self):
        self._fausser_horaire()

        call_command(
            "seed_taches_planifiees", reinitialiser_horaires=True,
            stdout=StringIO())

        tache = PeriodicTask.objects.get(name=self.NOM)
        self.assertEqual(tache.crontab.day_of_month, "31")
        self.assertEqual(tache.crontab.month_of_year, "12")
