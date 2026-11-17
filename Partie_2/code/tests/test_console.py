"""Mode interactif : une session saisie au clavier (simulee) produit les bons OK et REFUSE."""
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

CODE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)

SESSION = [
    "1", "3",                                   # Rita (rapporteuse) se connecte
    "5", "Clavier bloque", "haute",             # cree un ticket                    -> OK
    "6", "1",                                   # consulte le ticket de Remi        -> REFUSE (invisible)
    "9", "2", "trace.txt",                      # joint un texte a son ticket       -> OK
    "9", "2", "virus.exe",                      # joint un executable               -> REFUSE (fabrique)
    "7", "2",                                   # exporte son ticket en PDF         -> OK
    "0",
    "1", "2", "12",                             # Remi : Soumettre est masque pour un rapporteur
    "T", "12", "1", "0",                        # T affiche tout ; il tente quand meme -> REFUSE (SUBMIT)
    "1", "5", "12", "1", "13", "1", "0",        # Damien soumet -> OK ; valide son travail -> REFUSE
    "1", "4", "13", "1", "0",                   # Diane valide                      -> OK (TERMINE)
    "1", "1", "18", "1", "0",                   # Alice archive                     -> OK
    "1", "2", "10", "1", "merci", "0",          # Remi commente l'archive           -> REFUSE
    "2", "Zoe", "zoe@uqac.ca",                  # inscription                       -> OK
    "2", "Zoe bis", "ZOE@uqac.ca",              # email deja pris                   -> REFUSE
    "0",
]
ATTENDU = ["OK", "REFUSE", "OK", "REFUSE", "OK", "REFUSE", "OK", "REFUSE", "OK", "OK", "REFUSE", "OK", "REFUSE"]


def lancer(arguments, entree):
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, TICKETS_CONSOLE_BRUTE="1", TICKETS_UPLOAD_DIR=os.path.join(tmp, "up"),
                   TICKETS_EXPORT_DIR=os.path.join(tmp, "ex"), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "main.py"] + arguments, cwd=CODE, env=env, input=entree,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)


class TestConsole(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = lancer([], "\n".join(SESSION) + "\n")

    def test_session_complete(self):
        self.assertEqual(self.r.returncode, 0, self.r.stderr)
        self.assertNotIn("Traceback", self.r.stderr)
        self.assertIn("Au revoir.", self.r.stdout)

    def test_suite_des_resultats(self):
        # les invites de input() ne finissent pas la ligne : on cherche les verdicts partout
        obtenus = [v.rstrip(" :") for v in re.findall(r"  (OK :|REFUSE)", self.r.stdout)]
        self.assertEqual(obtenus, ATTENDU)

    def test_motifs_du_systeme_affiches(self):
        for motif in ("introuvable ou invisible", "extension non prise en charge", "SUBMIT : permission absente",
                      "l'assigne ne valide pas son propre travail", "archive : lecture et export seulement",
                      "email deja utilise"):
            self.assertIn(motif, self.r.stdout)

    def test_menu_selon_les_roles(self):
        self.assertIn("Action 12 non disponible pour vos roles", self.r.stdout)
        self.assertIn("12. Soumettre a validation *", self.r.stdout, "T affiche les actions hors des roles")

    def test_etats_affiches(self):
        self.assertIn("maintenant VALIDATION", self.r.stdout)
        self.assertIn("maintenant TERMINE", self.r.stdout)
        self.assertIn("La fabrique a cree un TextFileContent", self.r.stdout)

    def test_fin_d_entree_sans_erreur(self):
        for arguments, entree in (([], ""), ([], "1\n2\n6\n"), ([], ""), ([], "0\n")):
            with self.subTest(arguments=arguments, entree=entree):
                r = lancer(arguments, entree)
                self.assertEqual(r.returncode, 0)
                self.assertNotIn("Traceback", r.stderr + r.stdout)

    def test_pause_par_defaut_hors_terminal(self):
        """Sans TICKETS_CONSOLE_BRUTE (IDLE, console d'IDE), chaque action attend Entree."""
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, TICKETS_UPLOAD_DIR=os.path.join(tmp, "up"), TICKETS_EXPORT_DIR=os.path.join(tmp, "ex"),
                       PYTHONIOENCODING="utf-8")
            env.pop("TICKETS_CONSOLE_BRUTE", None)
            r = subprocess.run([sys.executable, "main.py"], cwd=CODE, env=env, input="1\n5\n13\n1\n\n0\n0\n",
                               capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Appuyez sur Entree pour revenir au menu", r.stdout)
        self.assertIn("Derniere action : REFUSE : valider est impossible en ASSIGNE", r.stdout)
        self.assertNotIn("\x1b[", r.stdout, "pas de couleurs hors d'un vrai terminal")

    def test_saisies_invalides(self):
        r = lancer([], "9\n1\nabc\n99\n1\n2\n42\n6\nxyz\n0\n0\n")
        self.assertEqual(r.returncode, 0)
        for message in ("Choix invalide", "Entrez un nombre entier", "Compte inconnu"):
            self.assertIn(message, r.stdout)



class TestMenuParRole(unittest.TestCase):
    """Le menu demande au modele (can_globally) ce que les roles permettent ; il ne contient aucune regle."""

    def menu_de(self, ident):
        r = lancer([], f"1\n{ident}\n0\n0\n")
        return r.stdout.split("Connecte :", 1)[1].split("Se deconnecter")[0]

    def test_rapporteur(self):
        menu = self.menu_de(2)
        for visible in ("1. Mes tickets", "5. Creer un ticket", "10. Commenter", "19. Mon profil"):
            self.assertIn(visible, menu)
        for masque in ("Tous les tickets", "Assigner", "Valider", "Archiver", "Lister les comptes", "Cycle de vie"):
            self.assertNotIn(masque, menu)

    def test_developpeur(self):
        menu = self.menu_de(4)
        for visible in ("2. Tous les tickets actifs", "11. Assigner", "13. Valider", "15. Fermer"):
            self.assertIn(visible, menu)
        for masque in ("Rouvrir", "Changer la priorite", "Archiver", "Lister les comptes"):
            self.assertNotIn(masque, menu)

    def test_administratrice_voit_tout(self):
        menu = self.menu_de(1)
        self.assertEqual(len(re.findall(r"\b(?:[1-9]|1\d|2[0-4])\. ", menu)), 24)

    def test_compte_desactive(self):
        r = lancer([], "1\n1\n23\n3\n0\n1\n3\n0\n0\n")
        menu = r.stdout.rsplit("Connecte :", 1)[1].split("Se deconnecter")[0]
        self.assertIn("19. Mon profil", menu)
        self.assertNotIn("Mes tickets", menu, "un compte desactive n'a plus aucune permission")


class TestEcranInteractif(unittest.TestCase):
    """Dans un vrai terminal : ecran efface avant chaque menu, une action par ecran, pause avant le retour."""

    def setUp(self):
        import logging
        niveau = logging.root.manager.disable  # d'autres modules de test coupent le journal
        logging.disable(logging.NOTSET)
        self.addCleanup(logging.disable, niveau)

    def test_effacement_pause_et_rappel(self):
        import console
        import donnees_demo
        from gestion_tickets.ticket import ContentFactory
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(donnees_demo, "TELEVERSEMENTS", tmp), \
                mock.patch.object(console, "TELEVERSEMENTS", tmp), \
                mock.patch.object(ContentFactory, "_ContentFactory__UPLOAD_DIR", tmp), \
                mock.patch("os.system") as systeme, \
                mock.patch("builtins.input", side_effect=["1", "5", "13", "1", "", "0", "0"]) as saisie, \
                redirect_stdout(io.StringIO()) as sortie:
            console.Console(ecran_interactif=True).lancer()
        effacements = [c for c in systeme.call_args_list if c.args and c.args[0] in ("cls", "clear")]
        self.assertGreaterEqual(len(effacements), 5, "menu, connexion, action, menu, accueil")
        invites = [c.args[0] for c in saisie.call_args_list]
        self.assertTrue(any("Appuyez sur Entree" in i for i in invites), "pause apres l'action")
        texte = sortie.getvalue()
        self.assertIn("valider est impossible en ASSIGNE", texte)
        self.assertIn("Derniere action : REFUSE : valider est impossible en ASSIGNE", texte)
        self.assertNotIn("motif : refus :", texte, "prefixe technique retire")


if __name__ == "__main__":
    unittest.main()
