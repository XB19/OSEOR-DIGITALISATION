"""
Événements de la vie interne : visibilité, calendrier, anniversaires
calculés et notifications du jour.
"""

from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from applications.evenements.models import Evenement
from applications.evenements.services import (
    _occurrence_anniversaire, anniversaires, anniversaires_du_jour,
    evenements_visibles, notifier_anniversaires_du_jour,
)
from applications.evenements.tasks import notifier_anniversaires_du_jour as tache
from applications.filiales.models import Filiale, Service
from applications.notifications.models import Notification

User = get_user_model()


def _instant(annee, mois, jour, heure=9):
    return timezone.make_aware(datetime(annee, mois, jour, heure))


class BaseEvenements:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")

        self.compta = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.kapi)
        self.moyens_generaux = Service.objects.create(
            nom="Moyens Généraux", code="MG", filiale=self.kapi)

        self.employe = User.objects.create_user(
            "employe", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.compta)
        self.collegue_mg = User.objects.create_user(
            "collegue_mg", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.moyens_generaux)
        self.employe_oseor = User.objects.create_user(
            "employe_oseor", password="x", role=User.Role.EMPLOYE,
            filiale=self.oseor)
        self.secretaire = User.objects.create_user(
            "secretaire", password="x", role=User.Role.SECRETAIRE,
            filiale=self.kapi)
        self.directeur = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)

    def creer_evenement(self, **surcharges):
        donnees = {
            "titre": "Vœux du Directeur Général",
            "type_evenement": Evenement.TypeEvenement.DISCOURS,
            "date_debut": _instant(2027, 1, 8),
            "date_fin": _instant(2027, 1, 8, 11),
            "filiale": self.kapi,
            "visibilite": Evenement.Visibilite.FILIALE,
            "createur": self.secretaire,
        }
        donnees.update(surcharges)
        return Evenement.objects.create(**donnees)


class ValidationTests(BaseEvenements, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_fin_avant_debut_refusee(self):
        evenement = Evenement(
            titre="Incohérent", date_debut=_instant(2027, 1, 8, 11),
            date_fin=_instant(2027, 1, 8, 9), filiale=self.kapi,
            createur=self.secretaire)
        with self.assertRaises(ValidationError):
            evenement.full_clean()

    def test_visibilite_service_sans_service_refusee(self):
        evenement = Evenement(
            titre="Réunion d'équipe", date_debut=_instant(2027, 1, 8),
            date_fin=_instant(2027, 1, 8, 10), filiale=self.kapi,
            visibilite=Evenement.Visibilite.SERVICE, createur=self.secretaire)
        with self.assertRaises(ValidationError):
            evenement.full_clean()

    def test_service_d_une_autre_filiale_refuse(self):
        autre_service = Service.objects.create(
            nom="Compta OSEOR", code="COMPTA", filiale=self.oseor)
        evenement = Evenement(
            titre="Incohérent", date_debut=_instant(2027, 1, 8),
            date_fin=_instant(2027, 1, 8, 10), filiale=self.kapi,
            service=autre_service, createur=self.secretaire)
        with self.assertRaises(ValidationError):
            evenement.full_clean()


class VisibiliteTests(BaseEvenements, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.groupe = self.creer_evenement(
            titre="Séminaire du groupe",
            visibilite=Evenement.Visibilite.GROUPE)
        self.filiale = self.creer_evenement(
            titre="Fête KAPI", visibilite=Evenement.Visibilite.FILIALE)
        self.service = self.creer_evenement(
            titre="Point Moyens Généraux",
            visibilite=Evenement.Visibilite.SERVICE,
            service=self.moyens_generaux)

    def _titres(self, utilisateur):
        return set(evenements_visibles(utilisateur).values_list("titre", flat=True))

    def test_direction_voit_tout(self):
        self.assertEqual(
            self._titres(self.directeur),
            {"Séminaire du groupe", "Fête KAPI", "Point Moyens Généraux"},
        )

    def test_membre_voit_groupe_et_sa_filiale(self):
        self.assertEqual(
            self._titres(self.employe), {"Séminaire du groupe", "Fête KAPI"})

    def test_membre_du_service_voit_son_evenement_de_service(self):
        self.assertIn("Point Moyens Généraux", self._titres(self.collegue_mg))

    def test_autre_filiale_ne_voit_que_le_groupe(self):
        self.assertEqual(
            self._titres(self.employe_oseor), {"Séminaire du groupe"})

    def test_compte_sans_filiale_ne_voit_que_le_groupe(self):
        isole = User.objects.create_user(
            "isole", password="x", role=User.Role.EMPLOYE)
        self.assertEqual(self._titres(isole), {"Séminaire du groupe"})


class AnniversairesTests(BaseEvenements, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.employe.date_naissance = date(1990, 3, 15)
        self.employe.save()
        self.employe_oseor.date_naissance = date(1985, 3, 20)
        self.employe_oseor.save()

    def test_occurrence_dans_la_fenetre(self):
        resultat = anniversaires(
            date(2027, 3, 1), date(2027, 3, 31), self.collegue_mg)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]["date"], date(2027, 3, 15))
        self.assertEqual(resultat[0]["age"], 37)

    def test_hors_fenetre_ignore(self):
        self.assertEqual(
            anniversaires(date(2027, 4, 1), date(2027, 4, 30), self.collegue_mg), [])

    def test_limite_a_la_filiale(self):
        """Un employé KAPI ne voit pas les anniversaires d'OSEOR."""
        resultat = anniversaires(
            date(2027, 3, 1), date(2027, 3, 31), self.collegue_mg)
        self.assertNotIn(
            self.employe_oseor.pk, [o["utilisateur_id"] for o in resultat])

    def test_direction_voit_tout_le_groupe(self):
        resultat = anniversaires(
            date(2027, 3, 1), date(2027, 3, 31), self.directeur)
        self.assertEqual(len(resultat), 2)

    def test_fenetre_a_cheval_sur_deux_annees(self):
        """Une fenêtre qui franchit le 31 décembre produit deux occurrences."""
        resultat = anniversaires(
            date(2027, 1, 1), date(2028, 12, 31), self.collegue_mg)
        self.assertEqual(
            [o["date"] for o in resultat],
            [date(2027, 3, 15), date(2028, 3, 15)],
        )

    def test_29_fevrier_celebre_le_28_les_annees_non_bissextiles(self):
        """Sans cette règle, la personne n'aurait un anniversaire qu'une
        année sur quatre."""
        self.assertEqual(
            _occurrence_anniversaire(date(2000, 2, 29), 2027), date(2027, 2, 28))
        self.assertEqual(
            _occurrence_anniversaire(date(2000, 2, 29), 2028), date(2028, 2, 29))

    def test_compte_inactif_exclu(self):
        """Un départ ne doit pas continuer à générer des anniversaires."""
        avant = anniversaires(date(2027, 3, 1), date(2027, 3, 31), self.directeur)
        self.assertIn(self.employe.pk, [o["utilisateur_id"] for o in avant])

        self.employe.is_active = False
        self.employe.save()

        apres = anniversaires(date(2027, 3, 1), date(2027, 3, 31), self.directeur)
        self.assertNotIn(self.employe.pk, [o["utilisateur_id"] for o in apres])

    def test_fenetre_inversee_renvoie_vide(self):
        self.assertEqual(
            anniversaires(date(2027, 3, 31), date(2027, 3, 1), self.directeur), [])

    def test_anniversaires_du_jour(self):
        celebres = anniversaires_du_jour(date(2027, 3, 15))
        self.assertEqual([u.pk for u in celebres], [self.employe.pk])


class NotificationAnniversaireTests(BaseEvenements, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.employe.date_naissance = date(1990, 3, 15)
        self.employe.save()

    def test_previent_les_collegues_de_la_filiale(self):
        envoyees = notifier_anniversaires_du_jour(date(2027, 3, 15))

        destinataires = set(
            Notification.objects.values_list("utilisateur_id", flat=True))
        self.assertEqual(
            destinataires,
            {self.collegue_mg.pk, self.secretaire.pk, self.directeur.pk},
        )
        self.assertEqual(envoyees, 3)

    def test_ne_previent_pas_l_interesse(self):
        notifier_anniversaires_du_jour(date(2027, 3, 15))
        self.assertFalse(
            Notification.objects.filter(utilisateur=self.employe).exists())

    def test_ne_deborde_pas_sur_une_autre_filiale(self):
        notifier_anniversaires_du_jour(date(2027, 3, 15))
        self.assertFalse(
            Notification.objects.filter(utilisateur=self.employe_oseor).exists())

    def test_aucun_anniversaire_aucune_notification(self):
        self.assertEqual(notifier_anniversaires_du_jour(date(2027, 6, 1)), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_appel_via_celery(self):
        resultat = tache.delay()
        self.assertTrue(resultat.successful())


class EvenementAPITests(BaseEvenements, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_creation_deduit_auteur_et_filiale(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.post("/api/evenements/", {
            "titre": "Pot de départ",
            "type_evenement": Evenement.TypeEvenement.RECEPTION,
            "date_debut": "2027-05-10T17:00:00Z",
            "date_fin": "2027-05-10T19:00:00Z",
        }, format="json")

        self.assertEqual(reponse.status_code, 201)
        evenement = Evenement.objects.get(titre="Pot de départ")
        self.assertEqual(evenement.createur, self.employe)
        self.assertEqual(evenement.filiale, self.kapi)

    def test_dates_incoherentes_refusees_en_400(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.post("/api/evenements/", {
            "titre": "Incohérent",
            "date_debut": "2027-05-10T19:00:00Z",
            "date_fin": "2027-05-10T17:00:00Z",
        }, format="json")
        self.assertEqual(reponse.status_code, 400)

    def test_anonyme_refuse(self):
        self.assertIn(
            self.client.get("/api/evenements/").status_code, (401, 403))

    def test_auteur_peut_modifier(self):
        evenement = self.creer_evenement(createur=self.employe)
        self.client.force_authenticate(self.employe)
        reponse = self.client.patch(
            f"/api/evenements/{evenement.pk}/", {"titre": "Corrigé"}, format="json")
        self.assertEqual(reponse.status_code, 200)

    def test_un_tiers_ne_peut_pas_modifier(self):
        evenement = self.creer_evenement(createur=self.secretaire)
        self.client.force_authenticate(self.employe)
        reponse = self.client.patch(
            f"/api/evenements/{evenement.pk}/", {"titre": "Détourné"}, format="json")
        self.assertEqual(reponse.status_code, 403)

    def test_direction_peut_modifier(self):
        evenement = self.creer_evenement(createur=self.employe)
        self.client.force_authenticate(self.directeur)
        reponse = self.client.patch(
            f"/api/evenements/{evenement.pk}/", {"titre": "Arbitré"}, format="json")
        self.assertEqual(reponse.status_code, 200)


class CalendrierAPITests(BaseEvenements, APITestCase):
    def setUp(self):
        self.creer_donnees()
        self.employe.date_naissance = date(1990, 3, 15)
        self.employe.save()
        self.evenement = self.creer_evenement(
            titre="Fête KAPI",
            date_debut=_instant(2027, 3, 20),
            date_fin=_instant(2027, 3, 20, 18))

    def _calendrier(self, utilisateur, debut="2027-03-01", fin="2027-03-31"):
        self.client.force_authenticate(utilisateur)
        return self.client.get(f"/api/evenements/calendrier/?debut={debut}&fin={fin}")

    def test_melange_evenements_et_anniversaires(self):
        reponse = self._calendrier(self.collegue_mg)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            [e["titre"] for e in reponse.data["evenements"]], ["Fête KAPI"])
        self.assertEqual(len(reponse.data["anniversaires"]), 1)

    def test_evenement_annule_masque(self):
        self.evenement.annule = True
        self.evenement.save()
        reponse = self._calendrier(self.collegue_mg)
        self.assertEqual(reponse.data["evenements"], [])

    def test_fenetre_par_defaut(self):
        self.client.force_authenticate(self.collegue_mg)
        reponse = self.client.get("/api/evenements/calendrier/")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            reponse.data["fin"] - reponse.data["debut"], timedelta(days=60))

    def test_dates_invalides_refusees(self):
        reponse = self._calendrier(self.collegue_mg, debut="pas-une-date")
        self.assertEqual(reponse.status_code, 400)

    def test_fin_avant_debut_refusee(self):
        reponse = self._calendrier(
            self.collegue_mg, debut="2027-03-31", fin="2027-03-01")
        self.assertEqual(reponse.status_code, 400)

    def test_perimetre_respecte(self):
        """Le calendrier applique la même visibilité que la liste."""
        reponse = self._calendrier(self.employe_oseor)
        self.assertEqual(reponse.data["evenements"], [])
