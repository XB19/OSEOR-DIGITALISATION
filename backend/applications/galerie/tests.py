"""
Galerie : albums, téléversement de photos, vignettes et contrôles d'entrée.

C'est le seul module qui accepte des fichiers binaires venus de
l'extérieur, et le seul capable de remplir un disque. Les contrôles
d'entrée sont donc testés sur de vraies images, générées à la volée —
pas sur des fichiers factices qui passeraient à côté de ce que Pillow
vérifie réellement.
"""

import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APITestCase

from applications.evenements.models import Evenement
from applications.filiales.models import Filiale, Service
from applications.galerie import services
from applications.galerie.imagerie import generer_miniature, valider_image
from applications.galerie.models import Album, Photo

User = get_user_model()

MEDIA_TEMPORAIRE = tempfile.mkdtemp(prefix="galerie-tests-")


def image_fichier(nom="photo.jpg", taille=(1200, 900), format_image="JPEG",
                  mode="RGB"):
    """Vraie image encodée, telle qu'un navigateur en enverrait une."""
    tampon = BytesIO()
    Image.new(mode, taille, (120, 160, 200)).save(tampon, format=format_image)
    tampon.seek(0)

    types = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif"}
    return SimpleUploadedFile(
        nom, tampon.getvalue(), content_type=types.get(format_image, "image/jpeg"))


class BaseGalerie:
    """Écrit dans un dossier temporaire, jamais dans le media du projet."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_TEMPORAIRE, ignore_errors=True)
        super().tearDownClass()

    def creer_donnees(self):
        self.kapi = Filiale.objects.create(nom="KAPI Consult", code="KAPI")
        self.oseor = Filiale.objects.create(nom="OSEOR SA", code="OSEOR")
        self.compta = Service.objects.create(
            nom="Comptabilité", code="COMPTA", filiale=self.kapi)

        self.employe = User.objects.create_user(
            "employe", password="x", role=User.Role.EMPLOYE,
            filiale=self.kapi, service=self.compta)
        self.collegue = User.objects.create_user(
            "collegue", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)
        self.employe_oseor = User.objects.create_user(
            "employe_oseor", password="x", role=User.Role.EMPLOYE,
            filiale=self.oseor)
        self.directeur = User.objects.create_user(
            "dg", password="x", role=User.Role.DIRECTEUR, filiale=self.kapi)

    def creer_album(self, **surcharges):
        donnees = {
            "titre": "Fête de fin d'année 2026",
            "filiale": self.kapi,
            "createur": self.employe,
            "visibilite": Album.Visibilite.FILIALE,
        }
        donnees.update(surcharges)
        return Album.objects.create(**donnees)


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAIRE)
class ValidationImageTests(TestCase):
    """Contrôles d'entrée : le seul rempart contre un fichier hostile."""

    def test_image_valide_acceptee(self):
        format_image, dimensions = valider_image(image_fichier())
        self.assertEqual(format_image, "JPEG")
        self.assertEqual(dimensions, (1200, 900))

    def test_fichier_qui_n_est_pas_une_image(self):
        faux = SimpleUploadedFile(
            "virus.jpg", b"MZ\x90\x00 ceci est un executable",
            content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            valider_image(faux)

    def test_extension_mensongere_rejetee(self):
        """
        L'extension et le type MIME viennent du client : seul l'en-tête
        réel du fichier fait foi.
        """
        faux = SimpleUploadedFile(
            "innocent.png", b"<?php system($_GET[0]); ?>",
            content_type="image/png")
        with self.assertRaises(ValidationError):
            valider_image(faux)

    def test_dimensions_excessives_refusees(self):
        with self.assertRaises(ValidationError):
            valider_image(image_fichier(taille=(9000, 100)))

    def test_le_curseur_est_rendu_intact(self):
        """Valider ne doit pas consommer le fichier : il est enregistré ensuite."""
        fichier = image_fichier()
        fichier.seek(4)

        valider_image(fichier)

        self.assertEqual(fichier.tell(), 4)


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAIRE)
class MiniatureTests(TestCase):
    def test_vignette_reduite_et_en_jpeg(self):
        vignette = generer_miniature(image_fichier(taille=(2000, 1000)))

        with Image.open(vignette) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertLessEqual(max(image.size), 480)

    def test_ratio_preserve(self):
        vignette = generer_miniature(image_fichier(taille=(2000, 1000)))
        with Image.open(vignette) as image:
            largeur, hauteur = image.size
        self.assertAlmostEqual(largeur / hauteur, 2.0, places=1)

    def test_png_transparent_aplati_sur_blanc(self):
        """
        JPEG ne connaît pas la transparence : sans aplatissement, les zones
        transparentes ressortiraient en noir.
        """
        vignette = generer_miniature(
            image_fichier(format_image="PNG", mode="RGBA"))

        self.assertIsNotNone(vignette)
        with Image.open(vignette) as image:
            self.assertEqual(image.mode, "RGB")

    def test_fichier_illisible_ne_bloque_pas(self):
        """Une vignette manquante dégrade l'affichage, elle n'empêche rien."""
        casse = SimpleUploadedFile("casse.jpg", b"pas une image")
        self.assertIsNone(generer_miniature(casse))


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAIRE)
class PhotoModeleTests(BaseGalerie, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.album = self.creer_album()

    def test_vignette_generee_a_l_enregistrement(self):
        photo = Photo.objects.create(
            album=self.album, image=image_fichier(),
            televersee_par=self.employe)

        self.assertTrue(photo.miniature)
        self.assertIn("_vignette", photo.miniature.name)

    def test_dimensions_et_taille_renseignees(self):
        photo = Photo.objects.create(
            album=self.album, image=image_fichier(taille=(800, 600)),
            televersee_par=self.employe)

        self.assertEqual((photo.largeur, photo.hauteur), (800, 600))
        self.assertGreater(photo.taille_octets, 0)

    def test_rangement_par_album(self):
        photo = Photo.objects.create(
            album=self.album, image=image_fichier(),
            televersee_par=self.employe)
        self.assertIn(f"galerie/{self.album.pk}/", photo.image.name)

    def test_suppression_efface_les_fichiers(self):
        """Sinon le volume garderait des images que plus rien ne référence."""
        import os

        photo = Photo.objects.create(
            album=self.album, image=image_fichier(),
            televersee_par=self.employe)
        chemin_image = photo.image.path
        chemin_vignette = photo.miniature.path

        photo.delete()

        self.assertFalse(os.path.exists(chemin_image))
        self.assertFalse(os.path.exists(chemin_vignette))


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAIRE)
class VisibiliteTests(BaseGalerie, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.groupe = self.creer_album(
            titre="Séminaire groupe", visibilite=Album.Visibilite.GROUPE)
        self.filiale = self.creer_album(
            titre="Fête KAPI", visibilite=Album.Visibilite.FILIALE)
        self.service = self.creer_album(
            titre="Pot Compta", visibilite=Album.Visibilite.SERVICE,
            service=self.compta)

    def _titres(self, utilisateur):
        return set(
            services.albums_visibles(utilisateur).values_list("titre", flat=True))

    def test_direction_voit_tout(self):
        self.assertEqual(
            self._titres(self.directeur),
            {"Séminaire groupe", "Fête KAPI", "Pot Compta"})

    def test_membre_du_service(self):
        self.assertEqual(
            self._titres(self.employe),
            {"Séminaire groupe", "Fête KAPI", "Pot Compta"})

    def test_autre_service_meme_filiale(self):
        self.assertEqual(
            self._titres(self.collegue), {"Séminaire groupe", "Fête KAPI"})

    def test_autre_filiale(self):
        self.assertEqual(self._titres(self.employe_oseor), {"Séminaire groupe"})

    def test_visibilite_service_sans_service_refusee(self):
        album = Album(
            titre="Incohérent", filiale=self.kapi, createur=self.employe,
            visibilite=Album.Visibilite.SERVICE)
        with self.assertRaises(ValidationError):
            album.full_clean()


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAIRE)
class DroitsTests(BaseGalerie, TestCase):
    def setUp(self):
        self.creer_donnees()
        self.album = self.creer_album(createur=self.employe)
        self.photo = Photo.objects.create(
            album=self.album, image=image_fichier(),
            televersee_par=self.collegue)

    def test_createur_gere_son_album(self):
        self.assertTrue(services.peut_gerer_album(self.album, self.employe))

    def test_un_tiers_ne_gere_pas(self):
        self.assertFalse(services.peut_gerer_album(self.album, self.collegue))

    def test_direction_gere(self):
        self.assertTrue(services.peut_gerer_album(self.album, self.directeur))

    def test_auteur_du_depot_retire_sa_photo(self):
        self.assertTrue(
            services.peut_supprimer_photo(self.photo, self.collegue))

    def test_proprietaire_de_l_album_retire_une_photo(self):
        self.assertTrue(services.peut_supprimer_photo(self.photo, self.employe))

    def test_un_collegue_quelconque_ne_retire_rien(self):
        """Une galerie d'entreprise n'est pas un mur ouvert."""
        autre = User.objects.create_user(
            "autre", password="x", role=User.Role.EMPLOYE, filiale=self.kapi)
        self.assertFalse(services.peut_supprimer_photo(self.photo, autre))


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAIRE)
class GalerieAPITests(BaseGalerie, APITestCase):
    def setUp(self):
        self.creer_donnees()

    def test_creation_album_deduit_createur_et_filiale(self):
        self.client.force_authenticate(self.employe)

        reponse = self.client.post("/api/albums/", {
            "titre": "Journée portes ouvertes",
            "visibilite": Album.Visibilite.FILIALE,
        }, format="json")

        self.assertEqual(reponse.status_code, 201)
        album = Album.objects.get(titre="Journée portes ouvertes")
        self.assertEqual(album.createur, self.employe)
        self.assertEqual(album.filiale, self.kapi)

    def test_album_rattache_a_un_evenement(self):
        from django.utils import timezone
        from datetime import datetime

        evenement = Evenement.objects.create(
            titre="Fête de fin d'année",
            date_debut=timezone.make_aware(datetime(2026, 12, 20, 18)),
            date_fin=timezone.make_aware(datetime(2026, 12, 20, 23)),
            filiale=self.kapi, createur=self.employe)

        self.client.force_authenticate(self.employe)
        reponse = self.client.post("/api/albums/", {
            "titre": "Photos de la fête", "evenement": evenement.pk,
        }, format="json")

        self.assertEqual(reponse.status_code, 201)

    def test_televersement(self):
        album = self.creer_album()
        self.client.force_authenticate(self.employe)

        reponse = self.client.post("/api/photos/", {
            "album": album.pk, "image": image_fichier(), "legende": "Discours du DG",
        }, format="multipart")

        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse.data["televersee_par"], self.employe.pk)
        self.assertTrue(reponse.data["miniature"])

    def test_televersement_d_un_faux_fichier_refuse(self):
        album = self.creer_album()
        self.client.force_authenticate(self.employe)

        reponse = self.client.post("/api/photos/", {
            "album": album.pk,
            "image": SimpleUploadedFile(
                "piege.jpg", b"pas une image", content_type="image/jpeg"),
        }, format="multipart")

        self.assertEqual(reponse.status_code, 400)

    def test_televersement_dans_un_album_inaccessible(self):
        album = self.creer_album(
            filiale=self.oseor, createur=self.employe_oseor)
        self.client.force_authenticate(self.employe)

        reponse = self.client.post("/api/photos/", {
            "album": album.pk, "image": image_fichier(),
        }, format="multipart")

        self.assertIn(reponse.status_code, (403, 400))

    def test_couverture_exposee(self):
        album = self.creer_album()
        Photo.objects.create(
            album=album, image=image_fichier(), televersee_par=self.employe)

        self.client.force_authenticate(self.employe)
        reponse = self.client.get(f"/api/albums/{album.pk}/")

        self.assertIsNotNone(reponse.data["couverture"])
        self.assertEqual(reponse.data["nb_photos"], 1)

    def test_suppression_photo_par_un_tiers_refusee(self):
        album = self.creer_album(createur=self.employe)
        photo = Photo.objects.create(
            album=album, image=image_fichier(), televersee_par=self.employe)

        self.client.force_authenticate(self.collegue)
        reponse = self.client.delete(f"/api/photos/{photo.pk}/")

        self.assertEqual(reponse.status_code, 403)

    def test_suppression_photo_par_son_auteur(self):
        album = self.creer_album(createur=self.employe)
        photo = Photo.objects.create(
            album=album, image=image_fichier(), televersee_par=self.collegue)

        self.client.force_authenticate(self.collegue)
        reponse = self.client.delete(f"/api/photos/{photo.pk}/")

        self.assertEqual(reponse.status_code, 204)
        self.assertFalse(Photo.objects.filter(pk=photo.pk).exists())

    def test_photos_limitees_aux_albums_visibles(self):
        album_oseor = self.creer_album(
            filiale=self.oseor, createur=self.employe_oseor)
        Photo.objects.create(
            album=album_oseor, image=image_fichier(),
            televersee_par=self.employe_oseor)

        self.client.force_authenticate(self.employe)
        reponse = self.client.get("/api/photos/")

        self.assertEqual(len(reponse.data.get("results", reponse.data)), 0)

    def test_anonyme_refuse(self):
        self.assertIn(self.client.get("/api/albums/").status_code, (401, 403))
