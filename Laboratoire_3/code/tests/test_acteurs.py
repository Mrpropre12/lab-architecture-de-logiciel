"""Tests du paquet acteurs : roles, permissions, comptes et registre."""
import logging
import unittest

from aide import MDP

from gestion_tickets.acteurs import (AdminRole, BaseRole, DeveloperRole, Permission,
                                     ReporterRole, Role, User, UserRegistry)

logging.disable(logging.CRITICAL)  # les refus sont journalises : silence pendant les tests

P = Permission
ROLES = (ReporterRole, DeveloperRole, AdminRole)


class TestRoles(unittest.TestCase):

    def test_interface_et_classe_abstraite(self):
        with self.assertRaises(TypeError):
            Role()
        with self.assertRaises(TypeError):
            BaseRole(frozenset())

    def test_chaque_permission_appartient_a_un_seul_role(self):
        vues = [p for cls in ROLES for p in cls().permissions()]
        self.assertEqual(len(vues), len(set(vues)), "permission partagee entre deux roles")
        self.assertEqual(set(vues), set(P), "permission orpheline")

    def test_contenu_des_roles(self):
        self.assertEqual(ReporterRole().permissions(),
                         {P.VIEW, P.COMMENT, P.EXPORT, P.CREATE, P.EDIT, P.ATTACH})
        self.assertEqual(DeveloperRole().permissions(),
                         {P.ASSIGN, P.SUBMIT, P.VALIDATE, P.REJECT, P.CLOSE, P.VIEW_ALL})
        self.assertEqual(AdminRole().permissions(),
                         {P.REOPEN, P.SET_PRIORITY, P.ARCHIVE, P.MANAGE_USERS})

    def test_allows(self):
        self.assertTrue(DeveloperRole().allows(P.ASSIGN))
        self.assertFalse(ReporterRole().allows(P.ASSIGN))
        self.assertFalse(ReporterRole().allows("VIEW"))  # une chaine n'est pas une permission

    def test_permissions_immuables(self):
        perms = ReporterRole().permissions()
        self.assertIsInstance(perms, frozenset)
        with self.assertRaises(AttributeError):
            perms.add(P.MANAGE_USERS)
        self.assertFalse(ReporterRole().allows(P.MANAGE_USERS))

    def test_egalite_et_hash_par_classe(self):
        self.assertEqual(ReporterRole(), ReporterRole())
        self.assertEqual(hash(AdminRole()), hash(AdminRole()))
        self.assertNotEqual(ReporterRole(), DeveloperRole())
        self.assertEqual(len({ReporterRole(), ReporterRole(), AdminRole()}), 2)
        self.assertNotEqual(ReporterRole(), "Rapporteur")

    def test_noms(self):
        self.assertEqual([c().name() for c in ROLES], ["Rapporteur", "Developpeur", "Administrateur"])


class BaseRegistre(unittest.TestCase):
    """Un registre avec un admin, une developpeuse et un rapporteur."""

    def setUp(self):
        self.reg = UserRegistry("Alice Admin", "alice@uqac.ca", MDP)
        self.admin = self._premier()
        self.dev = self.reg.register("Diane Dev", "diane@uqac.ca", MDP)
        self.rep = self.reg.register("Remi Rapporteur", "remi@uqac.ca", MDP)
        self.assertTrue(self.reg.grant_role(self.admin, self.dev, DeveloperRole()))

    def _premier(self):
        # find_by_id exige un acteur deja connu : on lit l'admin directement.
        for u in self._tous():
            if AdminRole() in u.get_roles():
                return u
        raise AssertionError("pas d'admin")

    def _tous(self):
        # Acces de test : le registre ne publie pas sa collection (aucun accesseur).
        return list(self.reg._UserRegistry__users.values())


class TestRegistreCreation(BaseRegistre):

    def test_premier_admin_a_les_trois_roles(self):
        self.assertEqual(self.admin.get_roles(), {ReporterRole(), DeveloperRole(), AdminRole()})
        self.assertEqual(self.admin.user_id, 1)

    def test_premier_admin_invalide(self):
        for nom, email in (("", "x@y.ca"), ("Nom", "pas-un-email")):
            with self.subTest(nom=nom, email=email):
                with self.assertRaises(ValueError):
                    UserRegistry(nom, email, MDP)

    def test_registres_independants(self):
        """Aucun etat global : deux registres coexistent et ne reconnaissent que leurs comptes."""
        autre = UserRegistry("Eve", "eve@ailleurs.ca", MDP)
        eve = autre.register("Eve2", "eve2@ailleurs.ca", MDP)
        self.assertTrue(autre.contains(eve))
        self.assertFalse(self.reg.contains(eve))
        self.assertTrue(self.reg.contains(self.rep))
        self.assertFalse(self.reg.contains(None))
        self.assertFalse(self.reg.contains(User(self.rep.user_id, "Remi", "remi@uqac.ca")), "copie forgee")

    def test_inscription_donne_reporter_seul(self):
        self.assertEqual(self.rep.get_roles(), {ReporterRole()})
        self.assertTrue(self.rep.active)

    def test_identifiants_successifs(self):
        self.assertEqual([self.admin.user_id, self.dev.user_id, self.rep.user_id], [1, 2, 3])
        self.assertEqual(self.reg.next_id, 4)

    def test_email_unique_sans_tenir_compte_de_la_casse(self):
        self.assertIsNone(self.reg.register("Copie", "REMI@uqac.ca", MDP))
        self.assertIsNone(self.reg.register("Copie", "  remi@uqac.ca ", MDP))
        self.assertEqual(self.reg.next_id, 4, "un refus ne consomme pas d'identifiant")

    def test_inscriptions_invalides(self):
        for nom, email in (("", "a@b.ca"), ("   ", "a@b.ca"), (None, "a@b.ca"), ("Nom", ""),
                           ("Nom", "sans-arobase"), ("Nom", "a@b"), ("Nom", None), ("Nom", 42)):
            with self.subTest(nom=nom, email=email):
                self.assertIsNone(self.reg.register(nom, email, MDP))

    def test_email_non_public(self):
        self.assertFalse(hasattr(self.rep, "email"))
        self.assertFalse(hasattr(self.rep, "get_email"))
        self.assertEqual(self.rep._get_email(), "remi@uqac.ca")

    def test_get_roles_est_une_copie_immuable(self):
        roles = self.rep.get_roles()
        with self.assertRaises(AttributeError):
            roles.add(AdminRole())
        self.assertFalse(self.rep.can_globally(P.MANAGE_USERS))

    def test_attributs_en_lecture_seule(self):
        with self.assertRaises(AttributeError):
            self.rep.user_id = 99
        with self.assertRaises(AttributeError):
            self.rep.active = False


class TestDroitsGlobaux(BaseRegistre):

    def test_cumul_des_roles(self):
        self.assertTrue(self.dev.can_globally(P.VIEW))       # vient de ReporterRole
        self.assertTrue(self.dev.can_globally(P.ASSIGN))     # vient de DeveloperRole
        self.assertFalse(self.dev.can_globally(P.ARCHIVE))
        self.assertFalse(self.rep.can_globally(P.ASSIGN))

    def test_compte_desactive_ne_peut_plus_rien(self):
        self.assertTrue(self.reg.deactivate(self.admin, self.dev))
        for p in P:
            self.assertFalse(self.dev.can_globally(p), p)


class TestRecherche(BaseRegistre):

    def test_find_by_id_comptes_actifs(self):
        self.assertIs(self.reg.find_by_id(self.rep, self.dev.user_id), self.dev)
        self.assertIsNone(self.reg.find_by_id(self.rep, 999))

    def test_compte_desactive_visible_seulement_avec_manage_users(self):
        self.reg.deactivate(self.admin, self.dev)
        self.assertIsNone(self.reg.find_by_id(self.rep, self.dev.user_id))
        self.assertIs(self.reg.find_by_id(self.admin, self.dev.user_id), self.dev)

    def test_acteur_desactive_ou_etranger(self):
        self.reg.deactivate(self.admin, self.rep)
        self.assertIsNone(self.reg.find_by_id(self.rep, 1))
        intrus = User(1, "Eve", "eve@ailleurs.ca")      # compte forge par le constructeur ~
        intrus._add_role(AdminRole())
        self.assertIsNone(self.reg.find_by_id(intrus, 1))
        self.assertEqual(self.reg.find_all(intrus), [])

    def test_identifiants_invalides(self):
        for mauvais in ("1", None, 1.0, True, [1]):
            with self.subTest(id=mauvais):
                self.assertIsNone(self.reg.find_by_id(self.admin, mauvais))

    def test_find_all(self):
        self.assertEqual(self.reg.find_all(self.admin), [self.admin, self.dev, self.rep])
        self.assertEqual(self.reg.find_all(self.dev), [])
        self.assertEqual(self.reg.find_all(None), [])


class TestGestionDesRoles(BaseRegistre):

    def test_seul_manage_users_attribue(self):
        self.assertFalse(self.reg.grant_role(self.dev, self.rep, DeveloperRole()))
        self.assertFalse(self.reg.grant_role(self.rep, self.rep, AdminRole()))
        self.assertEqual(self.rep.get_roles(), {ReporterRole()})

    def test_admin_implique_developpeur(self):
        self.assertTrue(self.reg.grant_role(self.admin, self.rep, AdminRole()))
        self.assertEqual(self.rep.get_roles(), {ReporterRole(), DeveloperRole(), AdminRole()})

    def test_pas_de_doublon(self):
        self.assertFalse(self.reg.grant_role(self.admin, self.dev, DeveloperRole()))
        self.assertEqual(len(self.dev.get_roles()), 2)

    def test_arguments_invalides(self):
        self.assertFalse(self.reg.grant_role(self.admin, self.rep, "AdminRole"))
        self.assertFalse(self.reg.grant_role(self.admin, None, AdminRole()))
        self.assertFalse(self.reg.revoke_role(self.admin, self.rep, None))

    def test_reporter_ne_se_retire_jamais(self):
        self.assertFalse(self.reg.revoke_role(self.admin, self.rep, ReporterRole()))
        self.assertFalse(self.reg.revoke_role(self.admin, self.admin, ReporterRole()))

    def test_developpeur_d_un_admin_ne_se_retire_pas(self):
        self.assertFalse(self.reg.revoke_role(self.admin, self.admin, DeveloperRole()))

    def test_retrait_normal(self):
        self.assertTrue(self.reg.revoke_role(self.admin, self.dev, DeveloperRole()))
        self.assertFalse(self.dev.can_globally(P.ASSIGN))
        self.assertFalse(self.reg.revoke_role(self.admin, self.dev, DeveloperRole()))

    def test_dernier_admin_actif_garde_son_role(self):
        self.assertFalse(self.reg.revoke_role(self.admin, self.admin, AdminRole()))
        self.assertTrue(self.reg.grant_role(self.admin, self.dev, AdminRole()))
        self.assertTrue(self.reg.revoke_role(self.admin, self.admin, AdminRole()))

    def test_verrouillage_avec_admin_desactive(self):
        """Scenario de la relecture : B est admin mais desactive, A ne peut pas partir."""
        self.reg.grant_role(self.admin, self.dev, AdminRole())
        self.assertTrue(self.reg.deactivate(self.admin, self.dev))
        self.assertFalse(self.reg.revoke_role(self.admin, self.admin, AdminRole()))
        self.assertFalse(self.reg.deactivate(self.admin, self.admin))
        self.assertTrue(self.admin.can_globally(P.MANAGE_USERS))


class TestActivation(BaseRegistre):

    def test_seul_manage_users_desactive(self):
        self.assertFalse(self.reg.deactivate(self.dev, self.rep))
        self.assertTrue(self.rep.active)

    def test_desactiver_puis_reactiver(self):
        self.assertTrue(self.reg.deactivate(self.admin, self.rep))
        self.assertFalse(self.reg.deactivate(self.admin, self.rep))
        self.assertTrue(self.reg.reactivate(self.admin, self.rep))
        self.assertFalse(self.reg.reactivate(self.admin, self.rep))
        self.assertTrue(self.rep.can_globally(P.VIEW))

    def test_le_compte_garde_ses_roles(self):
        self.reg.deactivate(self.admin, self.dev)
        self.assertIn(DeveloperRole(), self.dev.get_roles())
        self.reg.reactivate(self.admin, self.dev)
        self.assertTrue(self.dev.can_globally(P.ASSIGN))

    def test_dernier_admin_actif_ne_se_desactive_pas(self):
        self.assertFalse(self.reg.deactivate(self.admin, self.admin))

    def test_admin_desactive_ne_gere_plus_rien(self):
        self.reg.grant_role(self.admin, self.dev, AdminRole())
        self.reg.deactivate(self.dev, self.admin)
        self.assertFalse(self.reg.reactivate(self.admin, self.admin))
        self.assertFalse(self.reg.grant_role(self.admin, self.rep, AdminRole()))
        self.assertTrue(self.reg.reactivate(self.dev, self.admin))

    def test_cible_hors_registre(self):
        self.assertFalse(self.reg.deactivate(self.admin, User(1, "Eve", "eve@ailleurs.ca")))


if __name__ == "__main__":
    unittest.main()
