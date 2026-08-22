"""
Notes internes : diffusion automatique à la signature, accusés de lecture
et suivi de prise de connaissance.

Une note interne est un `Document` de type NOTE_INTERNE — elle hérite de la
numérotation, de la chaîne de visas et du journal d'audit du moteur
documentaire. Ce qui est testé ici, c'est ce que le module ajoute.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from applications.documents.models import (
    ConfigurationDocument, Document, TypeDocument,
)
from applications.filiales.models import Filiale, Service
from applications.notes.models import LectureNote
from applications.notes import services
from applications.notifications.models import Notification

User = get_user_model()


class BaseNotes:
    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")
        self.compta = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.kapi)

        ConfigurationDocument.objects.create(
            filiale=self.kapi,
            type_document=TypeDocument.NOTE_INTERNE,
            colonnes=[],
            visas=[
                {"cle": "redacteur", "libelle": "Rédigée par"},
                {"cle": "directeur_general", "libelle": "Visa du DG",
                 "role": "DIRECTEUR"},
            ],
        )

        self.secretaire = User.objects.create_user(
            "secretaire", password="x", role=User.Role.SECRETAIRE,
            filiale=self.kapi)
        self.employe = User.objects.create_user(
            "employe", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.compta)
        self.comptable = User.objects.create_user(
            "comptable", password="x", role=User.Role.COMPTABLE,
            filiale=self.kapi, service=self.compta)
        self.employe_oseor = User.objects.create_user(
            "employe_oseor", password="x", role=User.Role.EMPLOYE,
            filiale=self.oseor)
        self.directeur = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)

    def creer_note(self, statut=Document.Statut.EN_COURS, entete=None, **surcharges):
        donnees = {
            "filiale": self.kapi,
            "type_document": TypeDocument.NOTE_INTERNE,
            "demandeur": self.secretaire,
            "numero": f"KAPI-NI-2026-{Document.objects.count() + 1:04d}",
            "champs_entete": entete if entete is not None else {
                "objet": "Horaires d'été",
                "corps": "Les bureaux ferment à 15h les vendredis de juillet.",
            },
            "statut": statut,
            "etape_visa_courante": 1,
        }
        donnees.update(surcharges)
        return Document.objects.create(**donnees)


class DiffusionTests(BaseNotes, TestCase):
    def setUp(self):
        self.creer_donnees()

    def test_note_signee_diffusee_a_la_filiale(self):
        note = self.creer_note(statut=Document.Statut.VALIDE)

        destinataires = set(
            LectureNote.objects.filter(note=note).values_list(
                "destinataire_id", flat=True))
        self.assertEqual(
            destinataires,
            {self.employe.pk, self.comptable.pk, self.directeur.pk},
        )

    def test_redacteur_exclu_de_sa_propre_note(self):
        note = self.creer_note(statut=Document.Statut.VALIDE)
        self.assertFalse(
            LectureNote.objects.filter(
                note=note, destinataire=self.secretaire).exists())

    def test_note_non_signee_non_diffusee(self):
        note = self.creer_note(statut=Document.Statut.EN_COURS)
        self.assertEqual(LectureNote.objects.filter(note=note).count(), 0)

    def test_note_refusee_non_diffusee(self):
        note = self.creer_note(statut=Document.Statut.REFUSE)
        self.assertEqual(LectureNote.objects.filter(note=note).count(), 0)

    def test_diffusion_declenchee_par_la_signature(self):
        """Le passage à VALIDE suffit : aucun appel explicite nécessaire."""
        note = self.creer_note(statut=Document.Statut.EN_COURS)
        self.assertEqual(LectureNote.objects.filter(note=note).count(), 0)

        note.statut = Document.Statut.VALIDE
        note.save()

        self.assertEqual(LectureNote.objects.filter(note=note).count(), 3)

    def test_destinataires_notifies(self):
        self.creer_note(statut=Document.Statut.VALIDE)
        self.assertEqual(
            Notification.objects.filter(titre="Nouvelle note interne").count(), 3)

    def test_diffusion_idempotente(self):
        """
        Le signal se déclenche à chaque sauvegarde : rediffuser ne doit ni
        dupliquer les destinataires ni renotifier.
        """
        note = self.creer_note(statut=Document.Statut.VALIDE)
        note.save()
        note.save()

        self.assertEqual(LectureNote.objects.filter(note=note).count(), 3)
        self.assertEqual(
            Notification.objects.filter(titre="Nouvelle note interne").count(), 3)

    def test_visibilite_groupe(self):
        note = self.creer_note(
            statut=Document.Statut.VALIDE,
            entete={"objet": "Vœux", "visibilite": "GROUPE"})
        self.assertIn(
            self.employe_oseor.pk,
            LectureNote.objects.filter(note=note).values_list(
                "destinataire_id", flat=True),
        )

    def test_visibilite_service(self):
        note = self.creer_note(
            statut=Document.Statut.VALIDE,
            entete={"objet": "Clôture", "visibilite": "SERVICE",
                    "service_id": self.compta.pk})
        self.assertEqual(
            set(LectureNote.objects.filter(note=note).values_list(
                "destinataire_id", flat=True)),
            {self.employe.pk, self.comptable.pk},
        )

    def test_visibilite_service_sans_service_ne_diffuse_rien(self):
        note = self.creer_note(
            statut=Document.Statut.VALIDE,
            entete={"objet": "Incomplet", "visibilite": "SERVICE"})
        self.assertEqual(LectureNote.objects.filter(note=note).count(), 0)

    def test_filiale_par_defaut(self):
        """Sans visibilité précisée, une note ne part jamais à tout le groupe."""
        note = self.creer_note(
            statut=Document.Statut.VALIDE, entete={"objet": "Sans périmètre"})
        self.assertNotIn(
            self.employe_oseor.pk,
            LectureNote.objects.filter(note=note).values_list(
                "destinataire_id", flat=True),
        )

    def test_compte_inactif_exclu(self):
        self.employe.is_active = False
        self.employe.save()
        note = self.creer_note(statut=Document.Statut.VALIDE)
        self.assertNotIn(
            self.employe.pk,
            LectureNote.objects.filter(note=note).values_list(
                "destinataire_id", flat=True),
        )

    def test_un_autre_type_de_document_ne_diffuse_pas(self):
        Document.objects.create(
            filiale=self.kapi, type_document=TypeDocument.FICHE_BESOIN,
            demandeur=self.secretaire, numero="KAPI-FB-2026-0001",
            statut=Document.Statut.VALIDE)
        self.assertEqual(LectureNote.objects.count(), 0)


class LectureTests(BaseNotes, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.note = self.creer_note(statut=Document.Statut.VALIDE)

    def test_marquer_lue(self):
        lecture = services.marquer_lue(self.note, self.employe)
        self.assertIsNotNone(lecture.date_lecture)

    def test_premiere_lecture_fait_foi(self):
        premiere = services.marquer_lue(self.note, self.employe)
        horodatage = premiere.date_lecture

        seconde = services.marquer_lue(self.note, self.employe)

        self.assertEqual(seconde.date_lecture, horodatage)

    def test_non_destinataire_ignore(self):
        self.assertIsNone(services.marquer_lue(self.note, self.employe_oseor))

    def test_statistiques(self):
        services.marquer_lue(self.note, self.employe)

        stats = services.statistiques_diffusion(self.note)

        self.assertEqual(stats["destinataires"], 3)
        self.assertEqual(stats["lues"], 1)
        self.assertEqual(stats["non_lues"], 2)
        self.assertNotIn(
            self.employe.pk, [e["utilisateur_id"] for e in stats["en_attente"]])


class NoteAPITests(BaseNotes, APITestCase):
    def setUp(self):
        self.creer_donnees()
        self.note = self.creer_note(statut=Document.Statut.VALIDE)

    def test_liste_limitee_a_mes_notes(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.get("/api/notes-recues/")
        resultats = reponse.data.get("results", reponse.data)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["objet"], "Horaires d'été")

    def test_redacteur_ne_recoit_pas_sa_note(self):
        self.client.force_authenticate(self.secretaire)
        reponse = self.client.get("/api/notes-recues/")
        self.assertEqual(len(reponse.data.get("results", reponse.data)), 0)

    def test_filtre_non_lues(self):
        self.client.force_authenticate(self.employe)
        services.marquer_lue(self.note, self.employe)

        reponse = self.client.get("/api/notes-recues/?non_lues=1")
        self.assertEqual(len(reponse.data.get("results", reponse.data)), 0)

    def test_marquer_lue_par_l_api(self):
        lecture = LectureNote.objects.get(note=self.note, destinataire=self.employe)
        self.client.force_authenticate(self.employe)

        reponse = self.client.post(f"/api/notes-recues/{lecture.pk}/marquer_lue/")

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data["lue"])

    def test_marquer_lue_la_note_d_un_autre_impossible(self):
        lecture = LectureNote.objects.get(note=self.note, destinataire=self.employe)
        self.client.force_authenticate(self.comptable)

        reponse = self.client.post(f"/api/notes-recues/{lecture.pk}/marquer_lue/")

        self.assertEqual(reponse.status_code, 404)

    def test_suivi_de_diffusion_pour_le_redacteur(self):
        self.client.force_authenticate(self.secretaire)
        reponse = self.client.get(f"/api/notes-recues/diffusion/?note={self.note.pk}")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data["destinataires"], 3)

    def test_suivi_de_diffusion_pour_la_direction(self):
        self.client.force_authenticate(self.directeur)
        reponse = self.client.get(f"/api/notes-recues/diffusion/?note={self.note.pk}")
        self.assertEqual(reponse.status_code, 200)

    def test_suivi_de_diffusion_refuse_aux_autres(self):
        self.client.force_authenticate(self.employe)
        reponse = self.client.get(f"/api/notes-recues/diffusion/?note={self.note.pk}")
        self.assertEqual(reponse.status_code, 403)

    def test_suivi_sans_parametre(self):
        self.client.force_authenticate(self.secretaire)
        self.assertEqual(
            self.client.get("/api/notes-recues/diffusion/").status_code, 400)

    def test_anonyme_refuse(self):
        self.assertIn(
            self.client.get("/api/notes-recues/").status_code, (401, 403))
