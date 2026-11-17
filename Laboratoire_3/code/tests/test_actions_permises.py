"""Ticket.allowed_actions dit exactement ce que les actions acceptent.

Pour chaque etat (et l'archive), chaque acteur et chaque permission du ticket, on
compare la reponse de allowed_actions au resultat reel de l'action, tentee avec
des arguments valides sur un systeme neuf identique. Aucune regle n'est donc
recopiee : si une regle change dans une action, ce test le voit.
"""
import logging
import os
import tempfile
import unittest
from unittest import mock

from aide import MDP
from gestion_tickets.acteurs import DeveloperRole, Permission, UserRegistry
from gestion_tickets.consultation import PDFExportVisitor, ScreenRenderVisitor
from gestion_tickets.ticket import ContentFactory, Priority, Status, TicketRegistry

P = Permission
ACTIONS_DU_TICKET = [P.VIEW, P.EXPORT, P.COMMENT, P.EDIT, P.ATTACH, P.ASSIGN, P.SUBMIT, P.VALIDATE,
                     P.REJECT, P.CLOSE, P.REOPEN, P.SET_PRIORITY, P.ARCHIVE]
ETATS = ["OUVERT", "ASSIGNE", "VALIDATION", "TERMINE", "FERME", "ARCHIVE"]
ACTEURS = ["alice", "diane", "damien", "remi", "rita", "desactive", "etranger"]


def systeme(etat):
    """Un systeme neuf dont le ticket #1 (auteur Remi) est dans l'etat demande."""
    users = UserRegistry("Alice", "alice@uqac.ca", MDP)
    tickets = TicketRegistry(users)
    alice = users.authenticate("alice@uqac.ca", MDP)
    c = {"alice": alice}
    for nom in ("diane", "damien", "remi", "rita", "desactive"):
        c[nom] = users.register(nom.capitalize(), f"{nom}@uqac.ca", MDP)
    for nom in ("diane", "damien", "desactive"):
        users.grant_role(alice, c[nom], DeveloperRole())
    users.deactivate(alice, c["desactive"])
    c["etranger"] = UserRegistry("Eve", "eve@ailleurs.ca", MDP).authenticate("eve@ailleurs.ca", MDP)
    t = tickets.create(c["remi"], "Ecran noir", Priority.NORMALE)
    if etat != "OUVERT":
        assert t.assign(c["diane"], c["damien"])
    if etat in ("VALIDATION", "TERMINE", "ARCHIVE"):
        assert t.submit(c["damien"])
    if etat in ("TERMINE", "ARCHIVE"):
        assert t.validate(c["diane"])
    if etat == "FERME":
        assert t.close(c["diane"], "hors perimetre")
    if etat == "ARCHIVE":
        assert tickets.archive(alice, t.ticket_id)
    return users, tickets, t, c


def tenter(permission, tickets, t, acteur, c):
    """L'action reelle, avec des arguments valides."""
    if permission is P.VIEW:
        return t.consult(acteur, ScreenRenderVisitor())
    if permission is P.EXPORT:
        return t.export(acteur, PDFExportVisitor())
    if permission is P.COMMENT:
        return t.add_comment(acteur, "un commentaire")
    if permission is P.EDIT:
        return t.edit(acteur, "Nouveau titre")
    if permission is P.ATTACH:
        return t.add_content(acteur, ContentFactory.from_path("note.txt"))
    if permission is P.ASSIGN:
        autre = c["diane"] if t.get_assignee() is c["damien"] else c["damien"]
        return t.assign(acteur, autre)
    if permission is P.SUBMIT:
        return t.submit(acteur)
    if permission is P.VALIDATE:
        return t.validate(acteur)
    if permission is P.REJECT:
        return t.reject(acteur, "a revoir")
    if permission is P.CLOSE:
        return t.close(acteur, "doublon")
    if permission is P.REOPEN:
        return t.reopen(acteur, "le probleme revient")
    if permission is P.SET_PRIORITY:
        return t.set_priority(acteur, Priority.HAUTE)
    if permission is P.ARCHIVE:
        return tickets.archive(acteur, t.ticket_id)
    raise AssertionError(permission)


class TestActionsPermises(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.TemporaryDirectory()
        with open(os.path.join(cls.dossier.name, "note.txt"), "w", encoding="utf-8") as f:
            f.write("Etapes pour reproduire.")
        cls.televersement = mock.patch.object(ContentFactory, "_ContentFactory__UPLOAD_DIR", cls.dossier.name)
        cls.exports = tempfile.TemporaryDirectory()
        cls.export = mock.patch.object(PDFExportVisitor, "_PDFExportVisitor__EXPORT_DIR", cls.exports.name)
        cls.televersement.start()
        cls.export.start()

    @classmethod
    def tearDownClass(cls):
        cls.televersement.stop()
        cls.export.stop()
        cls.dossier.cleanup()
        cls.exports.cleanup()

    def test_allowed_actions_concorde_avec_les_actions(self):
        cas = 0
        for etat in ETATS:
            for nom in ACTEURS:
                _, _, t, c = systeme(etat)
                permises = t.allowed_actions(c[nom])
                for permission in ACTIONS_DU_TICKET:
                    _, tickets, t2, c2 = systeme(etat)
                    reel = bool(tenter(permission, tickets, t2, c2[nom], c2))
                    with self.subTest(etat=etat, acteur=nom, permission=permission.value):
                        self.assertEqual(permission in permises, reel)
                    cas += 1
        self.assertEqual(cas, len(ETATS) * len(ACTEURS) * len(ACTIONS_DU_TICKET))

    def test_aucun_effet_et_aucun_motif(self):
        _, _, t, c = systeme("VALIDATION")
        avant = (t.get_status(), t.get_assignee(), t.title, t.priority, t.update_date, t.next_comment_id)
        niveau = logging.root.manager.disable
        logging.disable(logging.NOTSET)
        self.addCleanup(logging.disable, niveau)
        with self.assertNoLogs("gestion_tickets", level=logging.INFO):
            for nom in ACTEURS:
                t.allowed_actions(c[nom])
        self.assertEqual(avant, (t.get_status(), t.get_assignee(), t.title, t.priority, t.update_date,
                                 t.next_comment_id))

    def journal(self):
        niveau = logging.root.manager.disable  # d'autres modules de test coupent le journal
        logging.disable(logging.NOTSET)
        self.addCleanup(logging.disable, niveau)

    def verifier_refus(self, action, attendu=False, motif="refus :"):
        """Convention du labo 2 : False (None pour un objet), et un motif au journal, que l'interface affiche."""
        with self.assertLogs("gestion_tickets", level=logging.INFO) as journal:
            logging.getLogger("gestion_tickets").info("temoin")  # assertLogs exige au moins une ligne
            resultat = action()
        self.assertIs(resultat, attendu)
        self.assertIn(motif, "\n".join(journal.output))

    def test_chaque_refus_renvoie_false_et_donne_son_motif(self):
        self.journal()
        for etat in ETATS:
            for nom in ACTEURS:
                for permission in ACTIONS_DU_TICKET:
                    _, tickets, t, c = systeme(etat)
                    if permission in t.allowed_actions(c[nom]):  # concordance prouvee par le test precedent
                        continue
                    attendu = None if permission is P.COMMENT else False
                    with self.subTest(etat=etat, acteur=nom, permission=permission.value):
                        self.verifier_refus(lambda: tenter(permission, tickets, t, c[nom], c), attendu)

    def test_refus_des_arguments(self):
        self.journal()
        _, _, t, c = systeme("OUVERT")
        remi, alice = c["remi"], c["alice"]
        self.assertTrue(t.add_content(remi, ContentFactory.from_path("note.txt")))
        self.assertIsNotNone(t.add_comment(remi, "x" * 5000), "5000 caracteres : la limite est permise")
        for motif, action, attendu in (
                ("titre vide", lambda: t.edit(remi, "   "), False),
                ("priorite invalide", lambda: t.set_priority(alice, "HAUTE"), False),
                ("la priorite est deja NORMALE", lambda: t.set_priority(alice, Priority.NORMALE), False),
                ("commentaire vide", lambda: t.add_comment(remi, ""), None),
                ("de plus de 5000 caracteres", lambda: t.add_comment(remi, "x" * 5001), None),
                ("ce n'est pas un contenu", lambda: t.add_content(remi, "note.txt"), False),
                ("fichier deja joint", lambda: t.add_content(remi, ContentFactory.from_path("note.txt")), False),
                ("consulter exige un ViewVisitor", lambda: t.consult(remi, PDFExportVisitor()), False)):
            with self.subTest(motif=motif):
                self.verifier_refus(action, attendu, motif)

    def test_contenu_remplace_apres_verification(self):
        self.journal()
        _, _, t, c = systeme("OUVERT")
        note = ContentFactory.from_path("note.txt")
        chemin = os.path.join(self.dossier.name, "note.txt")
        with open(chemin, "rb") as f:
            original = f.read()

        def restaurer():
            with open(chemin, "wb") as f:
                f.write(original)
        self.addCleanup(restaurer)
        with open(chemin, "wb") as f:
            f.write(b"\xff\xfe\xfa")  # remplace apres verification : n'est plus de l'UTF-8
        self.verifier_refus(lambda: t.add_content(c["remi"], note), False, "contenu non valide")

    def test_exemples_lisibles(self):
        _, _, t, c = systeme("VALIDATION")
        self.assertEqual(t.allowed_actions(c["damien"]) & {P.VALIDATE, P.REJECT, P.CLOSE}, {P.CLOSE},
                         "l'assigne ne valide ni ne rejette son propre travail")
        self.assertLessEqual({P.VALIDATE, P.REJECT, P.CLOSE}, t.allowed_actions(c["diane"]))
        self.assertEqual(t.allowed_actions(c["etranger"]), frozenset())
        self.assertEqual(t.allowed_actions(c["desactive"]), frozenset())
        _, _, archive, c = systeme("ARCHIVE")
        self.assertEqual(archive.allowed_actions(c["alice"]), {P.VIEW, P.EXPORT}, "archive en lecture seule")
        self.assertEqual(archive.get_status(), Status.TERMINE)


if __name__ == "__main__":
    unittest.main()
