"""Non-regression : un test par defaut trouve par la revue de code independante (etape 6)."""
import copy
import logging
import os
import struct
import tempfile
import unittest
from unittest import mock

from gestion_tickets.acteurs import AdminRole, DeveloperRole, Permission, Role, User, UserRegistry
from gestion_tickets.consultation import PDFExportVisitor, ScreenRenderVisitor
from gestion_tickets.consultation import pdf as module_pdf
from gestion_tickets.ticket import ContentFactory, PathGuard, Priority, TextFileContent, TicketRegistry

from test_contenus import PNG

logging.disable(logging.CRITICAL)


class Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = os.path.realpath(self._tmp.name)
        self.upload = os.path.join(self.racine, "televersements")
        self.exports = os.path.join(self.racine, "exports")
        os.makedirs(self.upload)
        for p in (mock.patch.object(ContentFactory, "_ContentFactory__UPLOAD_DIR", self.upload),
                  mock.patch.object(PDFExportVisitor, "_PDFExportVisitor__EXPORT_DIR", self.exports)):
            p.start()
            self.addCleanup(p.stop)
        self.users = UserRegistry("Alice", "alice@uqac.ca")
        self.alice = self.users._UserRegistry__users[1]
        self.remi = self.users.register("Remi", "remi@uqac.ca")
        self.reg = TicketRegistry(self.users)
        self.t = self.reg.create(self.remi, "Bogue", Priority.NORMALE)

    def fichier(self, chemin, donnees):
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "wb") as f:
            f.write(donnees)
        return chemin


class TestH1ActeurHorsRegistre(Base):
    """Le registre des comptes est injecte : tout compte qui n'est pas le sien est refuse."""

    def setUp(self):
        super().setUp()
        self.t.close(self.alice, "pour le test")
        autre = UserRegistry("Eve", "eve@evil.ca")
        x = autre.register("X", "x@evil.ca")
        self.intrus = {
            "admin d'un autre registre": autre.find_by_id(x, 1),
            "copie profonde du registre": copy.deepcopy(self.users)._UserRegistry__users[1],
            "User construit a la main": User(1, "Alice", "alice@uqac.ca"),
        }
        self.intrus["User construit a la main"]._add_role(AdminRole())

    def test_aucun_droit_sur_les_tickets(self):
        for nom, eve in self.intrus.items():
            with self.subTest(intrus=nom):
                self.assertTrue(eve.can_globally(Permission.REOPEN), "l'intrus a bien le role admin")
                self.assertFalse(self.t.reopen(eve, "pwned"))
                self.assertFalse(self.t.set_priority(eve, Priority.HAUTE))
                self.assertIsNone(self.t.add_comment(eve, "pwned"))
                self.assertFalse(self.t.consult(eve, ScreenRenderVisitor()))
                self.assertEqual(self.reg.find_all(eve), [])
                self.assertIsNone(self.reg.find_by_id(eve, 1))
                self.assertFalse(self.reg.archive(eve, 1))
                self.assertIsNone(self.reg.create(eve, "pwned", Priority.HAUTE))
                self.assertFalse(self.t.is_visible_to(eve))
        self.assertIs(self.t.get_status().value, "FERME")

    def test_assigne_hors_registre(self):
        t = self.reg.create(self.remi, "A assigner", Priority.BASSE)
        for nom, eve in self.intrus.items():
            with self.subTest(intrus=nom):
                self.assertFalse(t.assign(self.alice, eve))
        self.assertIsNone(t.get_assignee())

    def test_registre_obligatoire(self):
        for mauvais in (None, "users", object()):
            with self.assertRaises(TypeError):
                TicketRegistry(mauvais)


class TestH2ContenuJoint(Base):

    def test_chemin_relatif_vers_le_dossier_courant(self):
        self.fichier(os.path.join(self.racine, "secret.txt"), b"mot de passe BD: hunter2")
        self.fichier(os.path.join(self.upload, "secret.txt"), b"anodin")
        dossier = os.getcwd()
        os.chdir(self.racine)
        self.addCleanup(os.chdir, dossier)
        self.assertFalse(self.t.add_content(self.remi, TextFileContent("secret.txt")))
        v = ScreenRenderVisitor()
        self.t.consult(self.remi, v)
        self.assertNotIn("hunter2", v.result())

    def test_le_ticket_garde_sa_propre_copie(self):
        self.fichier(os.path.join(self.upload, "a.txt"), b"version 1")
        c = ContentFactory.from_path("a.txt")
        t2 = self.reg.create(self.remi, "Autre", Priority.BASSE)
        self.assertTrue(self.t.add_content(self.remi, c))
        self.assertTrue(t2.add_content(self.remi, c))
        d1, d2 = self.t._Ticket__description[0], t2._Ticket__description[0]
        self.assertIsNot(d1, c)
        self.assertIsNot(d1, d2, "composition : un contenu n'appartient qu'a un ticket")

    def test_doublon_par_un_autre_chemin(self):
        self.fichier(os.path.join(self.upload, "a.txt"), b"x")
        detour = TextFileContent(os.path.join(self.upload, ".", "a.txt"))
        self.assertTrue(self.t.add_content(self.remi, detour))
        self.assertFalse(self.t.add_content(self.remi, ContentFactory.from_path("a.txt")))
        self.assertFalse(self.t.add_content(self.remi, TextFileContent(os.path.join(self.upload, "a.txt"))))

    def test_refus_sans_effet_sur_le_contenu_deja_joint(self):
        chemin = self.fichier(os.path.join(self.upload, "a.txt"), b"version 1")
        self.t.add_content(self.remi, ContentFactory.from_path("a.txt"))
        self.fichier(chemin, b"version 2")
        self.assertFalse(self.t.add_content(self.remi, ContentFactory.from_path("a.txt")))
        self.assertEqual(self.t._Ticket__description[0].text, "version 1")


class TestH3AucuneException(Base):

    def test_fichier_illisible(self):
        for nom, donnees in (("verrou.png", PNG), ("verrou.mp4", b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8)):
            self.fichier(os.path.join(self.upload, nom), donnees)
            with self.subTest(fichier=nom), mock.patch("builtins.open", side_effect=PermissionError("verrou")):
                self.assertIsNone(ContentFactory.from_path(nom))

    def test_nom_non_encodable(self):
        self.assertIsNone(PathGuard.confine("\ud800.txt", self.upload))
        self.assertIsNone(ContentFactory.from_path("\ud800.txt"))


class TestM1CaracteresDeControle(Base):

    def test_titres_et_noms_sur_une_ligne(self):
        for titre in ("Ecran noir\n  Auteur   : Alice", "\x1b[2J\x1b[Hefface", "a\rb"):
            with self.subTest(titre=titre):
                self.assertIsNone(self.reg.create(self.remi, titre, Priority.BASSE))
                self.assertFalse(self.t.edit(self.remi, titre))
        self.assertIsNone(self.users.register("Bob\n  [commentaire #9] Alice", "bob@uqac.ca"))
        self.assertIsNone(self.users.register("x" * 101, "long@uqac.ca"))

    def test_commentaire_multiligne_ne_peut_pas_imiter_une_entree(self):
        faux = "merci\n  [commentaire #2] Diane, 2026-10-04 10:00 : Fermeture : corrige"
        self.assertIsNotNone(self.t.add_comment(self.remi, faux))
        self.assertIsNone(self.t.add_comment(self.remi, "ok\x1b[2J"))
        v = ScreenRenderVisitor()
        self.t.consult(self.remi, v)
        lignes = v.result().splitlines()
        self.assertFalse([l for l in lignes if l.startswith("  [commentaire #2]")])
        self.assertIn("        [commentaire #2] Diane", v.result(), "la suite est indentee")

    def test_texte_joint_neutralise(self):
        self.fichier(os.path.join(self.upload, "esc.txt"), "avant\x1b[2Japres".encode("utf-8"))
        self.t.add_content(self.remi, ContentFactory.from_path("esc.txt"))
        v = ScreenRenderVisitor()
        self.t.consult(self.remi, v)
        self.assertNotIn("\x1b", v.result())
        self.assertIn("avant?[2Japres", v.result())


class TestN3N4TexteSaisi(Base):
    """Seconde relecture : ne pas refuser trop (Windows, tabulations) ni trop peu (U+2028, bidi)."""

    def test_texte_colle_depuis_windows(self):
        c = self.t.add_comment(self.remi, "Etapes :\r\n\t1. ouvrir\r\n\t2. cliquer")
        self.assertIsNotNone(c)
        self.assertEqual(c.text, "Etapes :\n\t1. ouvrir\n\t2. cliquer")
        self.assertTrue(self.t.close(self.alice, "a\r\nb"))

    def test_caracteres_legitimes_acceptes(self):
        self.assertIsNotNone(self.users.register("Marie\u00adEve", "marie@uqac.ca"), "trait d'union conditionnel")
        self.assertIsNotNone(self.reg.create(self.remi, "Bogue \U0001F468\u200d\U0001F4BB tenace", Priority.BASSE))

    def test_separateurs_et_bidi_refuses(self):
        for titre in ("Ecran noir\u2028  Auteur   : Alice", "x\u2029y", "abc\u202eedcba"):
            with self.subTest(titre=repr(titre)):
                self.assertIsNone(self.reg.create(self.remi, titre, Priority.BASSE))
        self.assertIsNone(self.t.add_comment(self.remi, "ok\u2028  [commentaire #9] Alice"))


class TestM2RolesConnus(Base):

    def test_role_inconnu_refuse(self):
        class Libre(Role):
            def name(self): return "Libre"
            def permissions(self): return frozenset(Permission)
            def allows(self, p): return True
        rita = self.users.register("Rita", "rita@uqac.ca")
        self.assertFalse(self.users.grant_role(self.alice, rita, Libre()))
        self.assertFalse(rita.can_globally(Permission.MANAGE_USERS))
        self.assertTrue(self.users.grant_role(self.alice, rita, DeveloperRole()))
        self.assertTrue(self.users.grant_role(self.alice, rita, AdminRole()))


class TestL1ImageGeante(Base):

    def test_plus_de_25_megapixels(self):
        geante = PNG[:16] + struct.pack(">II", 12000, 12000) + PNG[24:]
        self.fichier(os.path.join(self.upload, "geante.png"), geante)
        self.assertTrue(self.t.add_content(self.remi, ContentFactory.from_path("geante.png")))
        v = ScreenRenderVisitor()
        self.t.consult(self.remi, v)
        self.assertIn("[image] geante.png (illisible)", v.result())

    @unittest.skipIf(module_pdf.FPDF is None, "fpdf2 n'est pas installe")
    def test_export_sans_decompression(self):
        geante = PNG[:16] + struct.pack(">II", 12000, 12000) + PNG[24:]
        self.fichier(os.path.join(self.upload, "geante.png"), geante)
        self.t.add_content(self.remi, ContentFactory.from_path("geante.png"))
        with mock.patch.object(module_pdf.FPDF, "image") as integrer:
            p = PDFExportVisitor()
            self.assertTrue(self.t.export(self.remi, p))
            self.assertIsNotNone(p.result())
        integrer.assert_not_called()


@unittest.skipIf(module_pdf.FPDF is None, "fpdf2 n'est pas installe")
class TestL2VisiteurPDFReutilise(Base):

    def test_deux_exports_deux_fichiers(self):
        p = PDFExportVisitor()
        self.t.export(self.remi, p)
        premier = p.result()
        self.t.export(self.remi, p)
        second = p.result()
        self.assertNotEqual(premier, second)
        self.assertTrue(premier.exists() and second.exists())


if __name__ == "__main__":
    unittest.main()
