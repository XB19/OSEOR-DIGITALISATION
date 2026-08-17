from datetime import date, time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase

from applications.filiales.models import Filiale
from applications.salles.models import Salle
from applications.reservations.models import Reservation, SerieRecurrence
from applications.reservations.services import generer_occurrences_serie

User = get_user_model()


class BaseDonnees:
    """Jeu de données commun aux tests."""

    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR", code="OSEOR")
        self.salle = Salle.objects.create(nom="Émeraude", filiale=self.kapi, capacite=10)

        self.employe = User.objects.create_user(
            "emp", password="x", role=User.Role.EMPLOYE, filiale=self.oseor)
        self.secretaire = User.objects.create_user(
            "sec", password="x", role=User.Role.SECRETAIRE, filiale=self.kapi)
        self.secretaire_autre = User.objects.create_user(
            "sec2", password="x", role=User.Role.SECRETAIRE, filiale=self.oseor)

    def reservation(self, hd="10:00", hf="12:00", statut=Reservation.Statut.VALIDEE):
        return Reservation.objects.create(
            demandeur=self.employe, nom_reservant="Paul", salle=self.salle,
            date_reunion=date(2030, 1, 6),
            heure_debut=time.fromisoformat(hd), heure_fin=time.fromisoformat(hf),
            statut=statut,
        )


class ChevauchementTests(BaseDonnees, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_chevauchement_bloque(self):
        """RG-01/EF-05 : un créneau qui chevauche une résa active est refusé."""
        self.reservation("10:00", "12:00")
        en_conflit = Reservation(
            demandeur=self.employe, nom_reservant="X", salle=self.salle,
            date_reunion=date(2030, 1, 6), heure_debut=time(11, 0), heure_fin=time(13, 0),
        )
        with self.assertRaises(ValidationError):
            en_conflit.save()

    def test_creneaux_adjacents_ok(self):
        """Deux créneaux qui se suivent (sans chevauchement) sont acceptés."""
        self.reservation("10:00", "11:00")
        suivant = Reservation(
            demandeur=self.employe, nom_reservant="X", salle=self.salle,
            date_reunion=date(2030, 1, 6), heure_debut=time(11, 0), heure_fin=time(12, 0),
        )
        suivant.save()  # ne doit pas lever
        self.assertEqual(Reservation.objects.count(), 2)

    def test_heure_fin_avant_debut_refusee(self):
        r = Reservation(
            demandeur=self.employe, nom_reservant="X", salle=self.salle,
            date_reunion=date(2030, 1, 6), heure_debut=time(12, 0), heure_fin=time(10, 0),
        )
        with self.assertRaises(ValidationError):
            r.save()


class ValidationAPITests(BaseDonnees, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_secretaire_filiale_peut_valider(self):
        r = self.reservation(statut=Reservation.Statut.EN_ATTENTE)
        self.client.force_authenticate(self.secretaire)
        rep = self.client.post(f"/api/reservations/{r.id}/valider/")
        self.assertEqual(rep.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reservation.Statut.VALIDEE)

    def test_secretaire_autre_filiale_refusee(self):
        """RG-02 : seul le secrétariat de la filiale propriétaire valide."""
        r = self.reservation(statut=Reservation.Statut.EN_ATTENTE)
        self.client.force_authenticate(self.secretaire_autre)
        rep = self.client.post(f"/api/reservations/{r.id}/valider/")
        self.assertEqual(rep.status_code, 403)

    def test_employe_ne_peut_pas_valider(self):
        r = self.reservation(statut=Reservation.Statut.EN_ATTENTE)
        self.client.force_authenticate(self.employe)
        rep = self.client.post(f"/api/reservations/{r.id}/valider/")
        self.assertEqual(rep.status_code, 403)

    def test_creation_via_api_remplit_demandeur(self):
        self.client.force_authenticate(self.employe)
        rep = self.client.post("/api/reservations/", {
            "salle": self.salle.id, "date_reunion": "2030-02-10",
            "heure_debut": "09:00", "heure_fin": "10:00", "motif": "Réunion",
        }, format="json")
        self.assertEqual(rep.status_code, 201)
        self.assertEqual(rep.data["statut"], "EN_ATTENTE")
        self.assertEqual(rep.data["demandeur"], self.employe.id)

    def test_disponibilite_signale_conflit(self):
        self.reservation("10:00", "12:00")
        self.client.force_authenticate(self.employe)
        rep = self.client.get("/api/reservations/verifier_disponibilite/", {
            "salle": self.salle.id, "date_reunion": "2030-01-06",
            "heure_debut": "11:00", "heure_fin": "13:00",
        })
        self.assertEqual(rep.status_code, 200)
        self.assertFalse(rep.data["disponible"])


class RecurrenceTests(BaseDonnees, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_generation_occurrences_hebdo(self):
        """EF-08 : une série hebdo génère une occurrence par jour ciblé."""
        serie = SerieRecurrence.objects.create(
            demandeur=self.employe, nom_reservant="Équipe", salle=self.salle,
            frequence=SerieRecurrence.Frequence.HEBDOMADAIRE, jours_semaine=[0],  # lundi
            heure_debut=time(9, 0), heure_fin=time(10, 0),
            date_debut=date(2030, 3, 4), date_fin=date(2030, 3, 25), motif="Hebdo",
        )
        creees, conflits = generer_occurrences_serie(serie)
        # lundis du 4 au 25 mars 2030 : 4, 11, 18, 25 -> 4 occurrences
        self.assertEqual(len(creees), 4)
        self.assertEqual(conflits, [])
        self.assertTrue(all(o.motif == "Hebdo" for o in creees))
