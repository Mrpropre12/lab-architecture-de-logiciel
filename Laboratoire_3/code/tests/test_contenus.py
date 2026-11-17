"""Tests de la description : contenus, fabrique, confinement et double dispatch."""
import logging
import os
import struct
import tempfile
import unittest
from unittest import mock

from gestion_tickets.ticket import (Content, ContentFactory, ExportVisitor, ImageFileContent,
                                   PathGuard, TextFileContent, TicketVisitor, VideoFileContent,
                                   ViewVisitor)

logging.disable(logging.CRITICAL)
MO = 1024 * 1024

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 640, 480) + b"\x08\x02\x00\x00\x00"
GIF = b"GIF89a" + struct.pack("<HH", 32, 16) + b"\x00\x00\x00"
JPG = (b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
       + b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 600, 800) + b"\x03" + b"\x00" * 9)
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16
MOV = b"\x00\x00\x00\x08wide" + b"\x00" * 16
AVI = b"RIFF\x00\x00\x00\x00AVI LIST" + b"\x00" * 16


class AvecDossier(unittest.TestCase):
    """Un UPLOAD_DIR temporaire, et un dossier voisin hors de la zone autorisee."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = os.path.realpath(self._tmp.name)
        self.upload = os.path.join(self.racine, "televersements")
        self.dehors = os.path.join(self.racine, "televersements2")  # meme prefixe, autre dossier
        os.makedirs(self.upload)
        os.makedirs(self.dehors)
        patch = mock.patch.object(ContentFactory, "_ContentFactory__UPLOAD_DIR", self.upload)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def fichier(self, nom, donnees, dossier=None):
        chemin = os.path.join(dossier or self.upload, nom)
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "wb") as f:
            f.write(donnees)
        return chemin

    def gros(self, nom, entete, taille):
        """Fichier creux : la taille est reelle sans ecrire des megaoctets."""
        chemin = self.fichier(nom, entete)
        with open(chemin, "r+b") as f:
            f.truncate(taille)
        return chemin


class TestPathGuard(AvecDossier):

    def test_chemin_interne(self):
        self.fichier("a/b.txt", b"x")
        self.assertEqual(PathGuard.confine("a/b.txt", self.upload), os.path.join(self.upload, "a", "b.txt"))
        self.assertIsNotNone(PathGuard.confine(os.path.join(self.upload, "a", "b.txt"), self.upload))

    def test_sorties_refusees(self):
        self.fichier("secret.txt", b"x", self.racine)
        for chemin in ("../secret.txt", "a/../../secret.txt", os.path.join(self.racine, "secret.txt"),
                       "../televersements2/x.txt", "/etc/passwd"):
            with self.subTest(chemin=chemin):
                self.assertIsNone(PathGuard.confine(chemin, self.upload))

    @unittest.skipIf(not hasattr(os, "symlink"), "liens symboliques indisponibles")
    def test_lien_symbolique_sortant(self):
        cible = self.fichier("secret.txt", b"x", self.racine)
        try:
            os.symlink(cible, os.path.join(self.upload, "lien.txt"))
        except OSError:
            self.skipTest("creation de lien refusee par le systeme")
        self.assertIsNone(PathGuard.confine("lien.txt", self.upload))

    def test_entrees_invalides(self):
        for chemin in ("", None, 42, "a\x00b.txt"):
            with self.subTest(chemin=chemin):
                self.assertIsNone(PathGuard.confine(chemin, self.upload))
        self.assertIsNone(PathGuard.confine("a.txt", None))


class TestFabrique(AvecDossier):

    def test_type_selon_l_extension(self):
        cas = {"note.txt": (b"bonjour", TextFileContent), "ecran.png": (PNG, ImageFileContent),
               "photo.JPG": (JPG, ImageFileContent), "photo.jpeg": (JPG, ImageFileContent),
               "anim.gif": (GIF, ImageFileContent), "demo.mp4": (MP4, VideoFileContent),
               "demo.mov": (MOV, VideoFileContent), "demo.avi": (AVI, VideoFileContent)}
        for nom, (donnees, attendu) in cas.items():
            with self.subTest(fichier=nom):
                self.fichier(nom, donnees)
                self.assertIsInstance(ContentFactory.from_path(nom), attendu)

    def test_refus(self):
        self.fichier("script.exe", b"MZ")
        self.fichier("sans_extension", b"x")
        os.makedirs(os.path.join(self.upload, "dossier.txt"))
        self.fichier("x.txt", b"x", self.dehors)
        for chemin in ("script.exe", "sans_extension", "absent.txt", "dossier.txt",
                       "../televersements2/x.txt", "", None):
            with self.subTest(chemin=chemin):
                self.assertIsNone(ContentFactory.from_path(chemin))

    def test_dossier_de_televersement_non_public(self):
        self.assertFalse(hasattr(ContentFactory, "UPLOAD_DIR"))
        self.assertFalse(hasattr(ContentFactory, "upload_dir"))


class TestTexte(AvecDossier):

    def test_lu_immediatement(self):
        self.fichier("note.txt", "Écran noir au démarrage".encode("utf-8"))
        c = ContentFactory.from_path("note.txt")
        self.assertTrue(c.loaded)
        self.assertEqual(c.text, "Écran noir au démarrage")

    def test_bom_windows_ignore(self):
        self.fichier("bom.txt", b"\xef\xbb\xbfbonjour")
        self.assertEqual(ContentFactory.from_path("bom.txt").text, "bonjour")

    def test_refus(self):
        self.fichier("latin1.txt", "é".encode("latin-1"))
        self.fichier("vide.txt", b"")
        self.gros("gros.txt", b"a", MO + 1)
        self.gros("limite.txt", b"a", MO)
        for nom in ("latin1.txt", "vide.txt", "gros.txt"):
            with self.subTest(fichier=nom):
                self.assertIsNone(ContentFactory.from_path(nom))
        self.assertIsNotNone(ContentFactory.from_path("limite.txt"), "1 Mo pile est accepte")


class TestImage(AvecDossier):

    def test_chargement_paresseux_et_cache(self):
        self.fichier("ecran.png", PNG)
        c = ContentFactory.from_path("ecran.png")
        self.assertFalse(c.loaded)
        self.assertIsNone(c.width)
        self.assertTrue(c.load())
        self.assertEqual((c.width, c.height), (640, 480))
        os.remove(c.path)               # le cache sert : pas de relecture
        self.assertTrue(c.load())
        c.unload()
        self.assertEqual((c.loaded, c.width, c.height), (False, None, None))
        self.assertFalse(c.load(), "apres unload, le fichier est relu")

    def test_dimensions_gif_et_jpeg(self):
        self.fichier("a.gif", GIF)
        self.fichier("b.jpg", JPG)
        gif, jpg = ContentFactory.from_path("a.gif"), ContentFactory.from_path("b.jpg")
        self.assertTrue(gif.load() and jpg.load())
        self.assertEqual((gif.width, gif.height), (32, 16))
        self.assertEqual((jpg.width, jpg.height), (800, 600))

    def test_refus(self):
        self.fichier("faux.png", b"ceci est un texte")
        self.fichier("gif_en_png.png", GIF)
        self.gros("grosse.png", PNG, 10 * MO + 1)
        for nom in ("faux.png", "gif_en_png.png", "grosse.png"):
            with self.subTest(fichier=nom):
                self.assertIsNone(ContentFactory.from_path(nom))

    def test_image_corrompue_valide_mais_illisible(self):
        self.fichier("tronquee.png", PNG[:12])
        c = ContentFactory.from_path("tronquee.png")
        self.assertIsNotNone(c)
        self.assertFalse(c.load())
        self.assertFalse(c.loaded)


class TestVideo(AvecDossier):

    def test_jamais_lue(self):
        self.fichier("demo.mp4", MP4)
        c = ContentFactory.from_path("demo.mp4")
        os.remove(c.path)                # load ne touche pas au fichier
        self.assertTrue(c.load())
        self.assertTrue(c.loaded)
        self.assertIsNone(c.duration)

    def test_refus(self):
        self.fichier("faux.mp4", b"pas une video du tout")
        self.fichier("avi_en_mp4.mp4", AVI)
        self.gros("enorme.mp4", MP4, 500 * MO + 1)
        for nom in ("faux.mp4", "avi_en_mp4.mp4", "enorme.mp4"):
            with self.subTest(fichier=nom):
                self.assertIsNone(ContentFactory.from_path(nom))


class Espion(TicketVisitor):
    def __init__(self):
        self.appels = []

    def visit_ticket(self, t): self.appels.append(("ticket", t))
    def visit_comment(self, c): self.appels.append(("comment", c))
    def visit_text(self, c): self.appels.append(("text", c))
    def visit_image(self, c): self.appels.append(("image", c))
    def visit_video(self, c): self.appels.append(("video", c))


class TestDoubleDispatch(AvecDossier):

    def test_chaque_contenu_appelle_sa_visite(self):
        self.fichier("a.txt", b"x")
        self.fichier("b.png", PNG)
        self.fichier("c.avi", AVI)
        contenus = [ContentFactory.from_path(n) for n in ("a.txt", "b.png", "c.avi")]
        espion = Espion()
        for c in contenus:
            c._accept(espion)
        self.assertEqual([a for a, _ in espion.appels], ["text", "image", "video"])
        self.assertEqual([c for _, c in espion.appels], contenus)

    def test_abstractions(self):
        for cls in (Content, TicketVisitor, ViewVisitor, ExportVisitor):
            with self.subTest(classe=cls.__name__):
                with self.assertRaises(TypeError):
                    cls("x") if cls is Content else cls()


if __name__ == "__main__":
    unittest.main()
