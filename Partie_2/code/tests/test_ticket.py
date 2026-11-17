"""Tests du coeur : cycle de vie, droits, regles contextuelles, archivage et recherches."""
import logging
import os
import tempfile
import time
import unittest
from unittest import mock

from gestion_tickets.acteurs import DeveloperRole, UserRegistry
from gestion_tickets.ticket import (Comment, ContentFactory, ExportVisitor, Priority, Status,
                                   TextFileContent, TicketRegistry, ViewVisitor)

logging.disable(logging.CRITICAL)
S = Status
TRANSITIONS = ("assign", "submit", "validate", "reject", "close", "reopen")
PERMISES = {S.OUVERT: {"assign", "close"},
            S.ASSIGNE: {"assign", "submit", "close"},
            S.VALIDATION: {"validate", "reject", "close"},
            S.TERMINE: {"reopen"},
            S.FERME: {"reopen"}}


class VueEspion(ViewVisitor):
    def __init__(self):
        self.appels = []

    def visit_ticket(self, t): self.appels.append("ticket")
    def visit_comment(self, c): self.appels.append("comment")
    def visit_text(self, c): self.appels.append("text")
    def visit_image(self, c): self.appels.append("image")
    def visit_video(self, c): self.appels.append("video")
    def result(self): return " ".join(self.appels)


class ExportEspion(ExportVisitor):
    def __init__(self):
        self.appels = []

    def visit_ticket(self, t): self.appels.append("ticket")
    def visit_comment(self, c): self.appels.append("comment")
    def visit_text(self, c): self.appels.append("text")
    def visit_image(self, c): self.appels.append("image")
    def visit_video(self, c): self.appels.append("video")
    def result(self): return None


class Ambigu(VueEspion, ExportVisitor):
    """Vue et export a la fois : refuse, sinon VIEW suffirait pour exporter."""
    def result(self): return None


class Base(unittest.TestCase):
    """Alice (admin), Diane et Damien (developpeurs), Remi et Rita (rapporteurs)."""

    def setUp(self):
        self.users = UserRegistry("Alice", "alice@uqac.ca")
        self.alice = self.users._UserRegistry__users[1]
        self.diane = self.users.register("Diane", "diane@uqac.ca")
        self.damien = self.users.register("Damien", "damien@uqac.ca")
        self.remi = self.users.register("Remi", "remi@uqac.ca")
        self.rita = self.users.register("Rita", "rita@uqac.ca")
        for dev in (self.diane, self.damien):
            self.users.grant_role(self.alice, dev, DeveloperRole())
        self.reg = TicketRegistry(self.users)
        self.t = self.reg.create(self.remi, "Ecran noir au demarrage", Priority.NORMALE)

    def amener(self, statut, t=None):
        """Amene un ticket dans un statut ; Damien est l'assigne, Alice valide et ferme."""
        t = t or self.t
        chemins = {
            S.OUVERT: [],
            S.ASSIGNE: [lambda: t.assign(self.alice, self.damien)],
            S.VALIDATION: [lambda: t.assign(self.alice, self.damien), lambda: t.submit(self.damien)],
            S.TERMINE: [lambda: t.assign(self.alice, self.damien), lambda: t.submit(self.damien),
                        lambda: t.validate(self.alice)],
            S.FERME: [lambda: t.close(self.alice, "doublon")],
        }
        for etape in chemins[statut]:
            self.assertTrue(etape())
        self.assertIs(t.get_status(), statut)
        return t

    def tenter(self, t, transition):
        """Chaque transition tentee par un acteur qui respecte les regles contextuelles."""
        return {"assign": lambda: t.assign(self.alice, self.diane),
                "submit": lambda: t.submit(self.damien),
                "validate": lambda: t.validate(self.alice),
                "reject": lambda: t.reject(self.alice, "incomplet"),
                "close": lambda: t.close(self.alice, "hors sujet"),
                "reopen": lambda: t.reopen(self.alice, "le bogue revient")}[transition]()

    def instantane(self, t):
        return (t.get_status(), t.get_assignee(), t.title, t.priority, t.update_date,
                t.next_comment_id, t.is_archived())


class TestCreation(Base):

    def test_etat_initial(self):
        self.assertEqual((self.t.ticket_id, self.t.get_status(), self.t.get_author(), self.t.get_assignee()),
                         (1, S.OUVERT, self.remi, None))
        self.assertEqual(self.t.creation_date, self.t.update_date)
        self.assertFalse(self.t.is_archived())
        self.assertIsNone(self.t.archive_date)

    def test_refus_de_creation(self):
        self.users.deactivate(self.alice, self.rita)
        for auteur, titre, p in ((self.rita, "x", Priority.BASSE), (None, "x", Priority.BASSE),
                                 (self.remi, "", Priority.BASSE), (self.remi, "   ", Priority.BASSE),
                                 (self.remi, "x" * 201, Priority.BASSE), (self.remi, None, Priority.BASSE),
                                 (self.remi, "x", "HAUTE"), (self.remi, "x", None)):
            with self.subTest(auteur=auteur, titre=titre, p=p):
                self.assertIsNone(self.reg.create(auteur, titre, p))
        self.assertEqual(self.reg.next_id, 2, "un refus ne consomme pas d'identifiant")

    def test_titre_nettoye_et_limite(self):
        self.assertEqual(self.reg.create(self.remi, "  Bogue  ", Priority.HAUTE).title, "Bogue")
        self.assertIsNotNone(self.reg.create(self.remi, "x" * 200, Priority.HAUTE))


class TestCycleDeVie(Base):

    def test_scenario_nominal(self):
        self.assertTrue(self.t.assign(self.diane, self.damien))
        self.assertEqual((self.t.get_status(), self.t.get_assignee()), (S.ASSIGNE, self.damien))
        self.assertTrue(self.t.submit(self.damien))
        self.assertIs(self.t.get_status(), S.VALIDATION)
        self.assertTrue(self.t.validate(self.diane))
        self.assertIs(self.t.get_status(), S.TERMINE)

    def test_matrice_complete_etats_transitions(self):
        """30 cas : chaque transition dans chaque etat, permise seulement si l'etat la redefinit."""
        for statut, permises in PERMISES.items():
            for transition in TRANSITIONS:
                with self.subTest(statut=statut.value, transition=transition):
                    t = self.amener(statut, self.reg.create(self.remi, "matrice", Priority.BASSE))
                    avant = self.instantane(t)
                    self.assertEqual(self.tenter(t, transition), transition in permises)
                    if transition not in permises:
                        self.assertEqual(self.instantane(t), avant, "un refus n'a aucun effet")
                    if t.get_status() is S.OUVERT:
                        self.assertIsNone(t.get_assignee(), "aucun assigne en OUVERT")

    def test_rejet_retour_a_assigne_avec_motif(self):
        self.amener(S.VALIDATION)
        self.assertTrue(self.t.reject(self.diane, "  les tests echouent "))
        self.assertEqual((self.t.get_status(), self.t.get_assignee()), (S.ASSIGNE, self.damien))
        visiteur = VueEspion()
        self.t.consult(self.remi, visiteur)
        self.assertEqual(visiteur.appels.count("comment"), 1)

    def test_motifs_conserves_en_commentaires(self):
        self.assertTrue(self.t.close(self.alice, "doublon du #4"))
        self.assertTrue(self.t.reopen(self.alice, "pas un doublon"))
        commentaires = self.t._Ticket__comments
        self.assertEqual([c.text for c in commentaires], ["Fermeture : doublon du #4", "Reouverture : pas un doublon"])
        self.assertEqual([c.get_author() for c in commentaires], [self.alice, self.alice])
        self.assertEqual([c.comment_id for c in commentaires], [1, 2])

    def test_motif_obligatoire(self):
        self.amener(S.VALIDATION)
        for motif in ("", "   ", None, 42):
            with self.subTest(motif=motif):
                avant = self.instantane(self.t)
                self.assertFalse(self.t.reject(self.alice, motif))
                self.assertFalse(self.t.close(self.alice, motif))
                self.assertEqual(self.instantane(self.t), avant)

    def test_reouverture_retire_l_assigne(self):
        self.amener(S.TERMINE)
        self.assertTrue(self.t.reopen(self.alice, "regression"))
        self.assertEqual((self.t.get_status(), self.t.get_assignee()), (S.OUVERT, None))

    def test_date_de_modification_avance(self):
        avant = self.t.update_date
        time.sleep(0.002)
        self.t.assign(self.diane, self.damien)
        self.assertGreater(self.t.update_date, avant)


class TestDroitsEtReglesContextuelles(Base):

    def test_rapporteur_ne_fait_pas_avancer_le_ticket(self):
        self.assertFalse(self.t.assign(self.remi, self.damien))
        self.assertFalse(self.t.close(self.remi, "je l'ai regle moi-meme"))
        self.amener(S.FERME)
        self.assertFalse(self.t.reopen(self.remi, "encore"))

    def test_developpeur_ne_reouvre_ni_ne_priorise(self):
        self.amener(S.FERME)
        self.assertFalse(self.t.reopen(self.diane, "encore"))
        self.assertFalse(self.t.set_priority(self.diane, Priority.HAUTE))

    def test_seul_l_assigne_soumet(self):
        self.amener(S.ASSIGNE)
        self.assertFalse(self.t.submit(self.diane))
        self.assertFalse(self.t.submit(self.alice))
        self.assertTrue(self.t.submit(self.damien))

    def test_l_assigne_ne_valide_ni_ne_rejette_son_travail(self):
        self.amener(S.VALIDATION)
        self.assertFalse(self.t.validate(self.damien))
        self.assertFalse(self.t.reject(self.damien, "je me rejette"))
        self.assertTrue(self.t.validate(self.diane))

    def test_l_assigne_doit_etre_un_developpeur_actif(self):
        self.assertFalse(self.t.assign(self.diane, self.remi))
        self.assertFalse(self.t.assign(self.diane, None))
        self.users.deactivate(self.alice, self.damien)
        self.assertFalse(self.t.assign(self.diane, self.damien))
        self.assertIs(self.t.get_status(), S.OUVERT)

    def test_reassignation_meme_si_l_assigne_est_desactive(self):
        self.amener(S.ASSIGNE)
        self.users.deactivate(self.alice, self.damien)
        self.assertFalse(self.t.submit(self.damien), "un compte desactive ne soumet plus")
        self.assertTrue(self.t.assign(self.diane, self.diane))
        self.assertIs(self.t.get_assignee(), self.diane)

    def test_reassignation_a_la_meme_personne_refusee(self):
        self.amener(S.ASSIGNE)
        self.assertFalse(self.t.assign(self.diane, self.damien))

    def test_acteur_desactive_ne_fait_plus_rien(self):
        self.users.deactivate(self.alice, self.remi)
        self.assertFalse(self.t.edit(self.remi, "nouveau"))
        self.assertIsNone(self.t.add_comment(self.remi, "allo"))
        self.assertFalse(self.t.consult(self.remi, VueEspion()))
        self.assertTrue(self.t.is_visible_to(self.remi), "la regle de visibilite reste vraie")

    def test_acteurs_invalides_sans_exception(self):
        for intrus in (None, "Alice", 42, object()):
            with self.subTest(acteur=intrus):
                for appel in (lambda: self.t.assign(intrus, self.damien), lambda: self.t.submit(intrus),
                              lambda: self.t.validate(intrus), lambda: self.t.reject(intrus, "x"),
                              lambda: self.t.close(intrus, "x"), lambda: self.t.reopen(intrus, "x"),
                              lambda: self.t.edit(intrus, "x"), lambda: self.t.set_priority(intrus, Priority.HAUTE),
                              lambda: self.t.consult(intrus, VueEspion()),
                              lambda: self.t.export(intrus, ExportEspion())):
                    self.assertFalse(appel())
                self.assertIsNone(self.t.add_comment(intrus, "x"))
                self.assertFalse(self.t.is_visible_to(intrus))


class TestModification(Base):

    def test_seul_l_auteur_modifie_le_titre(self):
        self.assertTrue(self.t.edit(self.remi, "  Ecran bleu "))
        self.assertEqual(self.t.title, "Ecran bleu")
        self.assertFalse(self.t.edit(self.diane, "Autre"))
        self.assertFalse(self.t.edit(self.alice, "Autre"))

    def test_modification_bloquee_en_termine_et_ferme(self):
        for statut in (S.TERMINE, S.FERME):
            with self.subTest(statut=statut.value):
                t = self.amener(statut, self.reg.create(self.remi, "titre", Priority.BASSE))
                self.assertFalse(t.edit(self.remi, "change"))

    def test_modifiable_en_assigne_et_validation(self):
        self.amener(S.VALIDATION)
        self.assertTrue(self.t.edit(self.remi, "precision"))

    def test_titres_invalides(self):
        for titre in ("", "  ", None, "x" * 201):
            self.assertFalse(self.t.edit(self.remi, titre))

    def test_priorite(self):
        self.assertTrue(self.t.set_priority(self.alice, Priority.HAUTE))
        self.assertIs(self.t.priority, Priority.HAUTE)
        self.assertFalse(self.t.set_priority(self.alice, Priority.HAUTE), "meme valeur : aucun effet")
        self.assertFalse(self.t.set_priority(self.alice, "BASSE"))


class TestCommentaires(Base):

    def test_ajout_et_numerotation(self):
        c1 = self.t.add_comment(self.remi, "Quand j'ouvre le portail")
        c2 = self.t.add_comment(self.diane, "Je regarde")
        self.assertIsInstance(c1, Comment)
        self.assertEqual((c1.comment_id, c2.comment_id, c1.get_author(), c2.text),
                         (1, 2, self.remi, "Je regarde"))
        self.assertEqual(self.t.next_comment_id, 3)

    def test_visibilite_exigee(self):
        self.assertIsNone(self.t.add_comment(self.rita, "je ne devrais pas voir ce ticket"))

    def test_permis_sur_ticket_ferme(self):
        self.amener(S.FERME)
        self.assertIsNotNone(self.t.add_comment(self.remi, "merci"))

    def test_commentaire_vide(self):
        for texte in ("", "  ", None):
            self.assertIsNone(self.t.add_comment(self.remi, texte))


class AvecTeleversement(Base):

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = os.path.realpath(self._tmp.name)
        self.upload = os.path.join(racine, "televersements")
        os.makedirs(self.upload)
        with open(os.path.join(self.upload, "trace.txt"), "w", encoding="utf-8") as f:
            f.write("Traceback ...")
        self.secret = os.path.join(racine, "secret.txt")
        with open(self.secret, "w", encoding="utf-8") as f:
            f.write("mot de passe")
        patch = mock.patch.object(ContentFactory, "_ContentFactory__UPLOAD_DIR", self.upload)
        patch.start()
        self.addCleanup(patch.stop)


class TestDescription(AvecTeleversement):

    def test_l_auteur_joint_un_fichier(self):
        self.assertTrue(self.t.add_content(self.remi, ContentFactory.from_path("trace.txt")))
        self.assertFalse(self.t.add_content(self.remi, ContentFactory.from_path("trace.txt")), "doublon")

    def test_autres_refus(self):
        c = ContentFactory.from_path("trace.txt")
        self.assertFalse(self.t.add_content(self.diane, c), "pas l'auteur")
        self.assertFalse(self.t.add_content(self.remi, "trace.txt"), "pas un contenu")
        self.assertFalse(self.t.add_content(self.remi, None))
        self.amener(S.FERME)
        self.assertFalse(self.t.add_content(self.remi, c), "ticket non modifiable")

    def test_contenu_construit_a_la_main_hors_du_dossier(self):
        """Python n'interdit pas d'appeler le constructeur ~ : add_content refait le controle."""
        forge = TextFileContent(self.secret)
        self.assertTrue(forge._is_valid(), "le fichier lui-meme est un texte valide")
        self.assertFalse(self.t.add_content(self.remi, forge))
        visiteur = VueEspion()
        self.t.consult(self.remi, visiteur)
        self.assertNotIn("text", visiteur.appels)


class TestConsultationEtExport(AvecTeleversement):

    def test_ordre_du_parcours(self):
        self.t.add_comment(self.remi, "precision")
        self.t.add_content(self.remi, ContentFactory.from_path("trace.txt"))
        visiteur = VueEspion()
        self.assertTrue(self.t.consult(self.remi, visiteur))
        self.assertEqual(visiteur.appels, ["ticket", "text", "comment"])

    def test_visibilite(self):
        self.assertTrue(self.t.consult(self.diane, VueEspion()), "VIEW_ALL")
        visiteur = VueEspion()
        self.assertFalse(self.t.consult(self.rita, visiteur))
        self.assertEqual(visiteur.appels, [], "aucune donnee transmise")
        self.assertFalse(self.t.export(self.rita, ExportEspion()))
        self.amener(S.ASSIGNE)
        self.assertTrue(self.t.is_visible_to(self.damien))

    def test_le_type_du_visiteur_fixe_la_permission(self):
        self.assertFalse(self.t.consult(self.remi, ExportEspion()), "un export ne passe pas par consult")
        self.assertFalse(self.t.export(self.remi, VueEspion()), "une vue ne passe pas par export")
        self.assertFalse(self.t.consult(self.remi, None))
        self.assertTrue(self.t.export(self.remi, ExportEspion()))
        self.assertFalse(self.t.consult(self.remi, Ambigu()))
        self.assertFalse(self.t.export(self.remi, Ambigu()))


class TestArchivage(Base):

    def test_seuls_termine_et_ferme_s_archivent(self):
        for statut in PERMISES:
            with self.subTest(statut=statut.value):
                t = self.amener(statut, self.reg.create(self.remi, "a archiver", Priority.BASSE))
                self.assertEqual(self.reg.archive(self.alice, t.ticket_id), statut in (S.TERMINE, S.FERME))

    def test_permission_et_arguments(self):
        self.amener(S.FERME)
        self.assertFalse(self.reg.archive(self.diane, 1))
        self.assertFalse(self.reg.archive(self.remi, 1))
        for mauvais in (999, "1", None, True):
            self.assertFalse(self.reg.archive(self.alice, mauvais))
        self.assertTrue(self.reg.archive(self.alice, 1))
        self.assertFalse(self.reg.archive(self.alice, 1), "deja archive")

    def test_archive_en_lecture_seule_et_definitive(self):
        self.amener(S.TERMINE)
        self.reg.archive(self.alice, 1)
        self.assertTrue(self.t.is_archived())
        self.assertIsNotNone(self.t.archive_date)
        avant = self.instantane(self.t)
        self.assertFalse(self.t.reopen(self.alice, "revient"))
        self.assertFalse(self.t.edit(self.remi, "x"))
        self.assertFalse(self.t.set_priority(self.alice, Priority.HAUTE))
        self.assertIsNone(self.t.add_comment(self.remi, "x"))
        self.assertEqual(self.instantane(self.t), avant)
        self.assertTrue(self.t.consult(self.remi, VueEspion()))
        self.assertTrue(self.t.export(self.remi, ExportEspion()))
        self.assertFalse(any(n for n in dir(self.reg) if "unarchive" in n or "restore" in n))


class TestRecherches(Base):

    def setUp(self):
        super().setUp()
        self.t2 = self.reg.create(self.rita, "Lenteur", Priority.HAUTE)
        self.t3 = self.reg.create(self.remi, "Faute de frappe", Priority.BASSE)
        self.amener(S.FERME, self.t3)
        self.reg.archive(self.alice, self.t3.ticket_id)
        self.amener(S.ASSIGNE, self.t2)

    def test_find_by_id(self):
        self.assertIs(self.reg.find_by_id(self.remi, 1), self.t)
        self.assertIsNone(self.reg.find_by_id(self.remi, 2), "ticket de Rita invisible pour Remi")
        self.assertIs(self.reg.find_by_id(self.damien, 2), self.t2)
        self.assertIs(self.reg.find_by_id(self.remi, 3), self.t3, "archive retrouvee par son auteur")
        for mauvais in ("1", None, 1.0, True, 999):
            self.assertIsNone(self.reg.find_by_id(self.alice, mauvais))

    def test_find_all(self):
        self.assertEqual(self.reg.find_all(self.diane), [self.t, self.t2], "sans les archives")
        self.assertEqual(self.reg.find_all(self.remi), [])

    def test_filtres(self):
        self.assertEqual(self.reg.find_by_author(self.remi, self.remi), [self.t])
        self.assertEqual(self.reg.find_by_author(self.remi, self.rita), [])
        self.assertEqual(self.reg.find_by_assignee(self.diane, self.damien), [self.t2])
        self.assertEqual(self.reg.find_by_status(self.diane, S.ASSIGNE), [self.t2])
        self.assertEqual(self.reg.find_by_status(self.diane, S.FERME), [], "le ferme est archive")
        self.assertEqual(self.reg.find_by_priority(self.diane, Priority.HAUTE), [self.t2])
        self.assertEqual(self.reg.find_by_status(self.diane, "ASSIGNE"), [])
        self.assertEqual(self.reg.find_by_priority(self.diane, None), [])

    def test_assigne_voit_son_ticket(self):
        self.users.revoke_role(self.alice, self.damien, DeveloperRole())
        self.assertEqual(self.reg.find_by_assignee(self.damien, self.damien), [self.t2])

    def test_find_archived(self):
        self.assertEqual(self.reg.find_archived(self.remi), [self.t3])
        self.assertEqual(self.reg.find_archived(self.rita), [])
        self.assertEqual(self.reg.find_archived(None), [])

    def test_acteur_desactive(self):
        self.users.deactivate(self.alice, self.diane)
        self.assertEqual(self.reg.find_all(self.diane), [])
        self.assertIsNone(self.reg.find_by_id(self.diane, 1))


if __name__ == "__main__":
    unittest.main()
