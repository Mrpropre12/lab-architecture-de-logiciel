"""Authentification par mot de passe (labo 3) : UserRegistry.register et authenticate."""
import logging
import unittest
from unittest import mock

from aide import MDP
from gestion_tickets.acteurs import UserRegistry
from gestion_tickets.acteurs import utilisateurs


class Journal(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class TestAuthentification(unittest.TestCase):

    def setUp(self):
        self.reg = UserRegistry("Alice", "alice@uqac.ca", MDP)
        self.alice = self.reg.authenticate("alice@uqac.ca", MDP)
        self.remi = self.reg.register("Remi", "remi@uqac.ca", "un long mot de passe")
        self.journal = Journal()
        journal = logging.getLogger("gestion_tickets")
        self.niveau = logging.root.manager.disable
        logging.disable(logging.NOTSET)
        journal.addHandler(self.journal)
        journal.setLevel(logging.INFO)
        self.addCleanup(journal.removeHandler, self.journal)
        self.addCleanup(logging.disable, self.niveau)

    # ------------------------------------------------ inscription
    def test_longueur_du_mot_de_passe(self):
        self.assertIsNone(self.reg.register("Court", "court@uqac.ca", "7carac."))
        self.assertIsNone(self.reg.register("Long", "long@uqac.ca", "x" * 129))
        self.assertIsNotNone(self.reg.register("Huit", "huit@uqac.ca", "8carac.."))
        self.assertIsNotNone(self.reg.register("Max", "max@uqac.ca", "x" * 128))

    def test_mot_de_passe_non_texte_refuse(self):
        for mdp in (None, 12345678, b"motdepasse"):
            with self.subTest(mdp=mdp):
                self.assertIsNone(self.reg.register("Bob", f"bob{id(mdp)}@uqac.ca", mdp))

    def test_phrase_de_passe_avec_espaces_et_accents(self):
        u = self.reg.register("Zoe", "zoe@uqac.ca", "été à Chicoutimi 2026")
        self.assertIs(self.reg.authenticate("zoe@uqac.ca", "été à Chicoutimi 2026"), u)

    def test_premier_admin_exige_un_mot_de_passe_valide(self):
        with self.assertRaises(ValueError):
            UserRegistry("Alice", "alice@uqac.ca", "court")

    # ------------------------------------------------ connexion
    def test_bon_mot_de_passe(self):
        self.assertIs(self.reg.authenticate("remi@uqac.ca", "un long mot de passe"), self.remi)

    def test_courriel_sans_casse_ni_espaces(self):
        self.assertIs(self.reg.authenticate("  REMI@uqac.ca ", "un long mot de passe"), self.remi)

    def test_mauvais_mot_de_passe_et_courriel_inconnu_ont_le_meme_motif(self):
        self.assertIsNone(self.reg.authenticate("remi@uqac.ca", "mauvais mot de passe"))
        self.assertIsNone(self.reg.authenticate("personne@uqac.ca", "un long mot de passe"))
        self.assertEqual(self.journal.messages[-2:], ["refus : courriel ou mot de passe incorrect"] * 2)

    def test_courriel_inconnu_coute_un_hachage(self):
        with mock.patch.object(utilisateurs, "_empreinte", wraps=utilisateurs._empreinte) as espion:
            self.reg.authenticate("personne@uqac.ca", "un long mot de passe")
        self.assertEqual(espion.call_count, 1, "meme travail qu'un mot de passe faux")

    def test_entrees_invalides(self):
        for email, mdp in ((None, MDP), ("remi@uqac.ca", None), ("remi@uqac.ca", "x" * 10_000)):
            with self.subTest(email=email, mdp=str(mdp)[:12]):
                self.assertIsNone(self.reg.authenticate(email, mdp))

    def test_compte_desactive_refuse_puis_reactive(self):
        self.assertTrue(self.reg.deactivate(self.alice, self.remi))
        self.assertIsNone(self.reg.authenticate("remi@uqac.ca", "un long mot de passe"))
        self.assertIn("compte desactive", self.journal.messages[-1])
        self.assertTrue(self.reg.reactivate(self.alice, self.remi))
        self.assertIs(self.reg.authenticate("remi@uqac.ca", "un long mot de passe"), self.remi)

    def test_normalisation_unicode(self):
        """NFKC : la ligature « ﬁ » et « fi » donnent le meme mot de passe."""
        u = self.reg.register("Fio", "fio@uqac.ca", "ﬁdele-au-poste")
        self.assertIs(self.reg.authenticate("fio@uqac.ca", "fidele-au-poste"), u)

    def test_registre_etranger(self):
        autre = UserRegistry("Eve", "eve@ailleurs.ca", MDP)
        self.assertIsNone(autre.authenticate("remi@uqac.ca", "un long mot de passe"))

    # ------------------------------------------------ stockage
    def test_mot_de_passe_jamais_stocke_en_clair(self):
        def fouiller(objet, vus):
            if id(objet) in vus:
                return
            vus.add(id(objet))
            if isinstance(objet, (str, bytes)):
                self.assertNotIn("un long mot de passe", objet if isinstance(objet, str) else objet.decode("latin-1"))
            elif isinstance(objet, dict):
                for k, v in objet.items():
                    fouiller(k, vus)
                    fouiller(v, vus)
            elif isinstance(objet, (list, tuple, set, frozenset)):
                for v in objet:
                    fouiller(v, vus)
            elif hasattr(objet, "__dict__"):
                fouiller(vars(objet), vus)
        fouiller(self.reg, set())

    def test_sel_different_pour_le_meme_mot_de_passe(self):
        b = self.reg.register("Bea", "bea@uqac.ca", "un long mot de passe")
        cred = self.reg._UserRegistry__credentials
        self.assertNotEqual(cred[self.remi.user_id][1], cred[b.user_id][1], "sel")
        self.assertNotEqual(cred[self.remi.user_id][2], cred[b.user_id][2], "empreinte")

    def test_chaque_empreinte_garde_son_nombre_d_iterations(self):
        ancien = UserRegistry.PBKDF2_ITERATIONS
        self.addCleanup(setattr, UserRegistry, "PBKDF2_ITERATIONS", ancien)
        UserRegistry.PBKDF2_ITERATIONS = ancien * 2
        self.assertIs(self.reg.authenticate("remi@uqac.ca", "un long mot de passe"), self.remi)

    def test_cout_par_defaut(self):
        """Les tests baissent le cout (aide.py) ; le code livre garde 600 000 iterations."""
        with open(utilisateurs.__file__, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("PBKDF2_ITERATIONS = 600_000", source, "recommandation OWASP 2023")

    def test_aucun_accesseur_aux_empreintes(self):
        self.assertFalse(hasattr(self.reg, "credentials"))


if __name__ == "__main__":
    unittest.main()
