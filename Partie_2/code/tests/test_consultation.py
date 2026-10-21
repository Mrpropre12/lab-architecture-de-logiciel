"""Tests des visiteurs concrets : rendu texte a l'ecran et export PDF."""
import io
import logging
import os
import re
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from gestion_tickets.acteurs import DeveloperRole, UserRegistry
from gestion_tickets.consultation import PDFExportVisitor, ScreenRenderVisitor
from gestion_tickets.consultation import pdf as module_pdf
from gestion_tickets.ticket import ContentFactory, Priority, TicketRegistry

from test_contenus import AVI, PNG

logging.disable(logging.CRITICAL)

try:
    from PIL import Image
except ImportError:
    Image = None


def texte_du_pdf(chemin) -> str:
    """Texte des flux du PDF (decompresses), sans bibliotheque externe."""
    brut = Path(chemin).read_bytes()
    morceaux = []
    for flux in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", brut, re.S):
        try:
            morceaux.append(zlib.decompress(flux).decode("latin-1"))
        except zlib.error:
            morceaux.append(flux.decode("latin-1", "replace"))
    return "".join(morceaux).replace("\\(", "(").replace("\\)", ")")  # parentheses echappees par le PDF


class Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = os.path.realpath(self._tmp.name)
        self.upload = os.path.join(racine, "televersements")
        self.exports = os.path.join(racine, "exports")
        os.makedirs(self.upload)
        for p in (mock.patch.object(ContentFactory, "_ContentFactory__UPLOAD_DIR", self.upload),
                  mock.patch.object(PDFExportVisitor, "_PDFExportVisitor__EXPORT_DIR", self.exports)):
            p.start()
            self.addCleanup(p.stop)
        self.users = UserRegistry("Alice", "alice@uqac.ca")
        self.alice = self.users._UserRegistry__users[1]
        self.damien = self.users.register("Damien", "damien@uqac.ca")
        self.users.grant_role(self.alice, self.damien, DeveloperRole())
        self.remi = self.users.register("Remi", "remi@uqac.ca")
        self.rita = self.users.register("Rita", "rita@uqac.ca")
        self.reg = TicketRegistry(self.users)
        self.t = self.reg.create(self.remi, "Ecran noir au demarrage", Priority.HAUTE)
        self.joindre("trace.txt", "Traceback (most recent call last):\n  KeyError: 'x'".encode("utf-8"))
        self.joindre("capture.png", self.png_reel() or PNG)
        self.joindre("demo.avi", AVI)
        self.t.assign(self.alice, self.damien)
        self.t.add_comment(self.remi, "Arrive a chaque redemarrage")

    def png_reel(self):
        if Image is None:
            return None
        tampon = io.BytesIO()
        Image.new("RGB", (64, 32), (200, 30, 30)).save(tampon, "PNG")
        return tampon.getvalue()

    def joindre(self, nom, donnees):
        with open(os.path.join(self.upload, nom), "wb") as f:
            f.write(donnees)
        self.assertTrue(self.t.add_content(self.remi, ContentFactory.from_path(nom)))


class TestEcran(Base):

    def test_rendu_complet(self):
        v = ScreenRenderVisitor()
        self.assertTrue(self.t.consult(self.remi, v))
        rendu = v.result()
        for attendu in ("Ticket #1", "[ASSIGNE]", "priorite HAUTE", "Ecran noir au demarrage",
                        "Auteur   : Remi", "Assigne : Damien", "[texte] trace.txt", "KeyError: 'x'",
                        "[image] capture.png", "[video] demo.avi (chemin conserve, non lue)",
                        "[commentaire #1] Remi"):
            self.assertIn(attendu, rendu)
        self.assertEqual(v.output, rendu)

    def test_ordre_ticket_description_commentaires(self):
        v = ScreenRenderVisitor()
        self.t.consult(self.remi, v)
        rendu = v.result()
        positions = [rendu.index(m) for m in ("Ticket #1", "[texte]", "[image]", "[video]", "[commentaire")]
        self.assertEqual(positions, sorted(positions))

    def test_image_chargee_au_premier_affichage(self):
        image = self.t._Ticket__description[1]
        self.assertFalse(image.loaded)
        v = ScreenRenderVisitor()
        self.t.consult(self.remi, v)
        self.assertTrue(image.loaded)
        self.assertIn(f"({image.width} x {image.height})", v.result())

    def test_nouveau_parcours_repart_a_zero(self):
        autre = self.reg.create(self.remi, "Deuxieme", Priority.BASSE)
        v = ScreenRenderVisitor()
        self.t.consult(self.remi, v)
        autre.consult(self.remi, v)
        self.assertNotIn("Ecran noir", v.result())
        self.assertIn("Deuxieme", v.result())

    def test_texte_long_tronque(self):
        t = self.reg.create(self.remi, "Long", Priority.BASSE)
        with open(os.path.join(self.upload, "long.txt"), "w", encoding="utf-8") as f:
            f.write("a" * 5000)
        t.add_content(self.remi, ContentFactory.from_path("long.txt"))
        v = ScreenRenderVisitor()
        t.consult(self.remi, v)
        self.assertIn("(4000 caracteres de plus)", v.result())

    def test_archive_et_ticket_invisible(self):
        v = ScreenRenderVisitor()
        self.assertFalse(self.t.consult(self.rita, v))
        self.assertEqual(v.result(), "", "rien n'est rendu pour un ticket invisible")
        self.t.close(self.alice, "doublon")
        self.reg.archive(self.alice, 1)
        self.t.consult(self.remi, v)
        self.assertIn("[FERME, archive le", v.result())

    def test_chemins_complets_jamais_affiches(self):
        v = ScreenRenderVisitor()
        self.t.consult(self.remi, v)
        self.assertNotIn(self.upload, v.result())


@unittest.skipIf(module_pdf.FPDF is None, "fpdf2 n'est pas installe")
class TestPDF(Base):

    def test_rien_avant_l_export(self):
        self.assertIsNone(PDFExportVisitor().result())

    def test_export_complet(self):
        v = PDFExportVisitor()
        self.assertTrue(self.t.export(self.remi, v))
        fichier = v.result()
        self.assertIsInstance(fichier, Path)
        self.assertTrue(fichier.read_bytes().startswith(b"%PDF"))
        texte = texte_du_pdf(fichier)
        for attendu in ("Ticket #1 : Ecran noir au demarrage", "Statut : ASSIGNE", "Auteur : Remi",
                        "[texte] trace.txt", "[image] capture.png", "[video] demo.avi", "Commentaire #1"):
            self.assertIn(attendu, texte)

    @unittest.skipIf(Image is None, "Pillow absent")
    def test_image_integree(self):
        v = PDFExportVisitor()
        self.t.export(self.remi, v)
        self.assertIn(b"/Subtype /Image", v.result().read_bytes())
        self.assertNotIn("non integrable", texte_du_pdf(v.result()))

    def test_image_corrompue_n_empeche_pas_l_export(self):
        t = self.reg.create(self.remi, "Image tronquee", Priority.BASSE)
        with open(os.path.join(self.upload, "tronquee.png"), "wb") as f:
            f.write(PNG[:12])
        t.add_content(self.remi, ContentFactory.from_path("tronquee.png"))
        v = PDFExportVisitor()
        self.assertTrue(t.export(self.remi, v))
        self.assertIn("(image non integrable)", texte_du_pdf(v.result()))

    def test_en_tete_valide_mais_corps_absent(self):
        """Les dimensions se lisent, mais fpdf2 ne peut pas decoder l'image : l'export continue."""
        t = self.reg.create(self.remi, "Image sans donnees", Priority.BASSE)
        with open(os.path.join(self.upload, "sans_idat.png"), "wb") as f:
            f.write(PNG)
        t.add_content(self.remi, ContentFactory.from_path("sans_idat.png"))
        v = PDFExportVisitor()
        self.assertTrue(t.export(self.remi, v))
        self.assertIn("(image non integrable)", texte_du_pdf(v.result()))

    def test_nom_unique_et_confine(self):
        a, b = PDFExportVisitor(), PDFExportVisitor()
        self.assertNotEqual(a.target_path, b.target_path)
        for v in (a, b):
            self.assertEqual(os.path.dirname(v.target_path), self.exports)
            self.assertTrue(os.path.basename(v.target_path).endswith(".pdf"))
        self.t.export(self.remi, a)
        self.assertEqual(os.path.dirname(a.result()), self.exports)

    def test_caracteres_hors_latin1(self):
        t = self.reg.create(self.remi, "Cœur l’écran … ✓ 🙂", Priority.BASSE)
        v = PDFExportVisitor()
        self.assertTrue(t.export(self.remi, v))
        self.assertIn("Coeur l'\xe9cran ...", texte_du_pdf(v.result()))

    def test_export_refuse_aucun_fichier(self):
        v = PDFExportVisitor()
        self.assertFalse(self.t.export(self.rita, v))
        self.assertIsNone(v.result())
        self.assertFalse(os.path.exists(self.exports) and os.listdir(self.exports))

    def test_archive_exportable(self):
        self.t.close(self.alice, "doublon")
        self.reg.archive(self.alice, 1)
        v = PDFExportVisitor()
        self.assertTrue(self.t.export(self.remi, v))
        self.assertIn("(archive le", texte_du_pdf(v.result()))


class TestSansFpdf(Base):

    def test_le_reste_fonctionne_sans_fpdf2(self):
        with mock.patch.object(module_pdf, "FPDF", None):
            v = PDFExportVisitor()
            self.assertTrue(self.t.export(self.remi, v), "le parcours a lieu")
            self.assertIsNone(v.result(), "mais aucun fichier n'est produit")
            self.assertTrue(self.t.consult(self.remi, ScreenRenderVisitor()))


if __name__ == "__main__":
    unittest.main()
