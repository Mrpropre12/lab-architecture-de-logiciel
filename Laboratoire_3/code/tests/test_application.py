"""Couche application : services, resultats, capture des motifs et import des fichiers (sans Qt)."""
import logging
import os
import sys
import tempfile
import unittest
from unittest import mock

import aide  # noqa: F401  (cout de hachage reduit pour les tests)
from gestion_tickets.ticket import ContentFactory

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
import donnees_demo  # noqa: E402
from application import (ASSIGNES_A_MOI, MES_TICKETS, TOUS, BlocImage, BlocTexte, CaptureMotif,  # noqa: E402
                         ImportFichiers, Permission, Priority, Resultat, Status, creer_application)


class Base(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.ailleurs = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.addCleanup(self.ailleurs.cleanup)
        for cible, valeur in ((ContentFactory, ("_ContentFactory__UPLOAD_DIR", self.dossier.name)),
                              (donnees_demo, ("TELEVERSEMENTS", self.dossier.name))):
            p = mock.patch.object(cible, *valeur)
            p.start()
            self.addCleanup(p.stop)
        with mock.patch("builtins.print"):
            users, tickets = donnees_demo.creer_systeme()
        self.session, self.comptes, self.tickets = creer_application(users, tickets, self.dossier.name)
        niveau = logging.root.manager.disable
        logging.disable(logging.NOTSET)
        self.addCleanup(logging.disable, niveau)

    def connecter(self, prenom):
        r = self.comptes.connecter(f"{prenom}@uqac.ca", f"{prenom}-2026")
        self.assertTrue(r.ok, r.motif)
        return r.valeur

    def image(self, nom="photo.png", donnees=None):
        chemin = os.path.join(self.ailleurs.name, nom)
        with open(chemin, "wb") as f:
            f.write(donnees if donnees is not None else donnees_demo.png(40, 30, (200, 10, 10)))
        return chemin

    def fichiers_televerses(self):
        return sorted(os.listdir(self.dossier.name))


class TestComptes(Base):

    def test_connexion(self):
        profil = self.connecter("alice")
        self.assertEqual(profil.nom, "Alice")
        self.assertEqual(profil.roles, ("Rapporteur", "Developpeur", "Administrateur"))
        self.assertIn(Permission.MANAGE_USERS, profil.permissions)
        self.assertEqual(self.session.connecte.name, "Alice")
        self.assertIs(self.session.peut(Permission.MANAGE_USERS), True)

    def test_connexion_refusee_motif_generique(self):
        for courriel, mdp in (("alice@uqac.ca", "faux-mdp-123"), ("personne@uqac.ca", "alice-2026")):
            r = self.comptes.connecter(courriel, mdp)
            self.assertFalse(r.ok)
            self.assertEqual(r.motif, "courriel ou mot de passe incorrect")
        self.assertIsNone(self.session.connecte)

    def test_deconnexion_et_actions_sans_compte(self):
        self.connecter("remi")
        self.assertTrue(self.comptes.deconnecter().ok)
        self.assertIsNone(self.session.connecte)
        for r in (self.comptes.profil(), self.comptes.lister(), self.comptes.desactiver(2), self.tickets.lister(),
                  self.tickets.valider(1), self.tickets.archives(), self.tickets.assignables(),
                  self.tickets.creer("Titre", Priority.BASSE), self.tickets.ajouter_texte(1, "texte"),
                  self.tickets.joindre_image(1, self.image())):
            self.assertEqual((r.ok, r.motif), (False, "aucun compte connecte"))
        self.assertEqual(self.tickets.actions_permises(1), frozenset())
        self.assertIs(self.session.peut(Permission.VIEW), False)

    def test_inscription(self):
        r = self.comptes.inscrire("Zoe", "zoe@uqac.ca", "zoe-motdepasse", "zoe-motdepasse")
        self.assertTrue(r.ok)
        self.assertTrue(self.comptes.connecter("zoe@uqac.ca", "zoe-motdepasse").ok)
        self.assertEqual(self.comptes.profil().valeur.roles, ("Rapporteur",))

    def test_inscription_refusee(self):
        r = self.comptes.inscrire("Zoe", "zoe@uqac.ca", "zoe-motdepasse", "zoe-motdepass")
        self.assertEqual(r.motif, "les deux mots de passe ne sont pas identiques")
        r = self.comptes.inscrire("Copie", "REMI@uqac.ca", "un-mot-de-passe", "un-mot-de-passe")
        self.assertIn("email deja utilise", r.motif)
        r = self.comptes.inscrire("Court", "court@uqac.ca", "court", "court")
        self.assertIn("mot de passe de 8 a 128 caracteres", r.motif)

    def test_gestion_reservee_a_manage_users(self):
        self.connecter("remi")
        self.assertIs(self.session.peut(Permission.MANAGE_USERS), False)
        r = self.comptes.lister()
        self.assertFalse(r.ok)
        self.assertIn("MANAGE_USERS", r.motif)

    def test_lister_et_desactiver(self):
        self.connecter("alice")
        comptes = self.comptes.lister().valeur
        self.assertEqual([c.nom for c in comptes], ["Alice", "Remi", "Rita", "Diane", "Damien"])
        self.assertTrue(self.comptes.desactiver(3).ok)
        self.assertFalse(self.comptes.lister().valeur[2].actif)
        self.comptes.deconnecter()
        r = self.comptes.connecter("rita@uqac.ca", "rita-2026")
        self.assertIn("compte desactive", r.motif)
        self.connecter("alice")
        self.assertEqual(self.comptes.reactiver(3).valeur, "Rita")
        self.assertTrue(self.comptes.lister().valeur[2].actif)

    def test_roles(self):
        self.connecter("alice")
        self.assertTrue(self.comptes.attribuer_role(2, "Developpeur").ok)
        self.assertEqual(self.comptes.lister().valeur[1].roles, ("Rapporteur", "Developpeur"))
        self.assertIn("ReporterRole ne se retire jamais", self.comptes.retirer_role(2, "Rapporteur").motif)
        self.assertEqual(self.comptes.attribuer_role(2, "Pirate").motif, "role inconnu : Pirate")
        self.assertEqual(self.comptes.retirer_role(2, "Pirate").motif, "role inconnu : Pirate")

    def test_se_desactiver_soi_meme_deconnecte(self):
        self.connecter("alice")
        self.assertTrue(self.comptes.attribuer_role(4, "Administrateur").ok)
        r = self.comptes.desactiver(1)
        self.assertTrue(r.ok)
        self.assertIn("vous avez ete deconnecte", r.details[0])
        self.assertIsNone(self.session.connecte)


class TestListes(Base):

    def numeros(self, r):
        self.assertTrue(r.ok, r.motif)
        return [ligne.numero for ligne in r.valeur]

    def test_mes_tickets(self):
        self.connecter("remi")
        self.assertEqual(self.numeros(self.tickets.lister(MES_TICKETS)), [1])
        self.connecter("damien")
        self.assertEqual(self.numeros(self.tickets.lister(MES_TICKETS)), [1], "assigne, sans doublon")
        self.assertEqual(self.numeros(self.tickets.lister(ASSIGNES_A_MOI)), [1])

    def test_tous_exige_view_all(self):
        self.connecter("remi")
        r = self.tickets.lister(TOUS)
        self.assertFalse(r.ok)
        self.assertIn("VIEW_ALL", r.motif)
        self.connecter("diane")
        self.assertEqual(self.numeros(self.tickets.lister(TOUS)), [1, 2])

    def test_filtres(self):
        self.connecter("diane")
        self.assertEqual(self.numeros(self.tickets.lister(TOUS, statut=Status.OUVERT)), [2])
        self.assertEqual(self.numeros(self.tickets.lister(TOUS, priorite=Priority.HAUTE)), [1])
        self.assertEqual(self.numeros(self.tickets.lister(TOUS, Status.OUVERT, Priority.HAUTE)), [])
        self.assertFalse(self.tickets.lister("n'importe quoi").ok)

    def test_ligne(self):
        self.connecter("remi")
        ligne = self.tickets.lister().valeur[0]
        self.assertEqual((ligne.titre, ligne.statut, ligne.priorite, ligne.auteur, ligne.assigne, ligne.archive),
                         ("Écran noir au démarrage du portail", Status.ASSIGNE, Priority.HAUTE, "Remi", "Damien",
                          False))

    def test_assignables(self):
        self.connecter("diane")
        self.assertEqual([c.nom for c in self.tickets.assignables().valeur], ["Alice", "Diane", "Damien"])


class TestCycleDeVie(Base):

    def test_detail_et_actions(self):
        self.connecter("damien")
        d = self.tickets.detail(1).valeur
        self.assertIn(Permission.SUBMIT, d.actions)
        self.assertNotIn(Permission.VALIDATE, d.actions)
        self.assertTrue(any(isinstance(b, BlocImage) for b in d.blocs))
        self.assertIn("Ticket 1", d.texte)

    def test_detail_invisible(self):
        self.connecter("rita")
        r = self.tickets.detail(1)
        self.assertFalse(r.ok)
        self.assertIn("introuvable ou invisible", r.motif)

    def test_parcours_complet(self):
        self.connecter("damien")
        self.assertTrue(self.tickets.soumettre(1).ok)
        r = self.tickets.valider(1)
        self.assertEqual((r.ok, r.motif), (False, "l'assigne ne valide pas son propre travail"))
        self.connecter("diane")
        self.assertTrue(self.tickets.rejeter(1, "un test manque").ok)
        self.connecter("damien")
        self.assertTrue(self.tickets.soumettre(1).ok)
        self.connecter("diane")
        self.assertTrue(self.tickets.valider(1).ok)
        self.connecter("alice")
        self.assertTrue(self.tickets.archiver(1).ok)
        self.assertEqual([t.numero for t in self.tickets.archives().valeur], [1])
        self.assertEqual(self.tickets.actions_permises(1), {Permission.VIEW, Permission.EXPORT})

    def test_motif_obligatoire(self):
        self.connecter("diane")
        self.assertIn("motif est obligatoire", self.tickets.fermer(1, "  ").motif)
        self.assertTrue(self.tickets.fermer(1, "doublon").ok)
        self.assertTrue(self.tickets.rouvrir(1, "revient").motif is not None)  # Diane n'a pas REOPEN

    def test_assigner_un_rapporteur_refuse(self):
        self.connecter("diane")
        r = self.tickets.assigner(2, 3)
        self.assertIn("developpeur actif", r.motif)
        self.assertTrue(self.tickets.assigner(2, 5).ok)

    def test_titre_commentaire_priorite(self):
        self.connecter("rita")
        self.assertTrue(self.tickets.modifier_titre(2, "Faute dans le menu Aide (accent)").ok)
        self.assertEqual(self.tickets.commenter(2, "Merci").valeur.text, "Merci")
        self.assertIn("SET_PRIORITY", self.tickets.changer_priorite(2, Priority.HAUTE).motif)


class TestCreationEtPiecesJointes(Base):

    def test_creer_avec_texte_et_image(self):
        self.connecter("rita")
        r = self.tickets.creer("Bouton invisible", Priority.NORMALE, "Etapes :\r\n1. Ouvrir", [self.image()])
        self.assertTrue(r.ok, r.motif)
        self.assertEqual(r.details, ())
        blocs = self.tickets.detail(r.valeur).valeur.blocs
        texte = next(b for b in blocs if isinstance(b, BlocTexte))
        self.assertEqual(texte.texte, "Etapes :\n1. Ouvrir\n")
        image = next(b for b in blocs if isinstance(b, BlocImage))
        self.assertEqual((image.largeur, image.hauteur), (40, 30))
        self.assertTrue(os.path.dirname(image.chemin) == os.path.realpath(self.dossier.name))

    def test_creation_refusee_et_texte_blanc_ignore(self):
        self.connecter("rita")
        r = self.tickets.creer("   ", Priority.BASSE)
        self.assertFalse(r.ok)
        self.assertIn("titre", r.motif)
        r = self.tickets.creer("Sans description", Priority.BASSE, "   \n ")
        self.assertEqual(r.details, (), "un texte fait de blancs n'est pas joint, sans erreur")
        self.assertFalse([b for b in self.tickets.detail(r.valeur).valeur.blocs if isinstance(b, BlocTexte)])

    def test_erreurs_du_disque(self):
        self.connecter("remi")
        with mock.patch("application.fichiers.shutil.copyfile", side_effect=OSError(13, "Permission denied")):
            self.assertEqual(self.tickets.joindre_image(1, self.image()).motif, "copie impossible : Permission denied")
        with mock.patch("application.fichiers.open", side_effect=OSError(28, "No space left on device"), create=True):
            self.assertEqual(self.tickets.ajouter_texte(1, "Note").motif,
                             "ecriture impossible : No space left on device")

    def test_une_image_reste_une_image(self):
        """Defense en profondeur : si la fabrique rendait un autre type, l'import serait refuse."""
        self.connecter("remi")
        with open(os.path.join(self.dossier.name, "note.txt"), "w", encoding="utf-8") as f:
            f.write("texte")
        texte = ContentFactory.from_path("note.txt")
        with mock.patch("application.fichiers.ContentFactory.from_path", return_value=texte):
            r = self.tickets.joindre_image(1, self.image())
        self.assertEqual((r.ok, r.motif), (False, "fichier refuse par la fabrique"))

    def test_piece_refusee_signalee_sans_annuler_le_ticket(self):
        self.connecter("rita")
        avant = self.fichiers_televerses()
        r = self.tickets.creer("Avec fausse image", Priority.BASSE, "", [self.image("faux.png", b"pas une image")])
        self.assertTrue(r.ok)
        self.assertEqual(len(r.details), 1)
        self.assertIn("image non jointe (faux.png)", r.details[0])
        self.assertEqual(self.fichiers_televerses(), avant, "la copie refusee est supprimee")

    def test_extension_refusee_avant_copie(self):
        self.connecter("remi")
        avant = self.fichiers_televerses()
        r = self.tickets.joindre_image(1, self.image("virus.exe", b"MZ"))
        self.assertEqual(r.motif, "seules les images .png, .jpg et .gif sont acceptees")
        self.assertEqual(self.fichiers_televerses(), avant)

    def test_texte_refuse_si_pas_auteur(self):
        self.connecter("damien")
        avant = self.fichiers_televerses()
        r = self.tickets.ajouter_texte(1, "Note de Damien")
        self.assertIn("seul l'auteur complete la description", r.motif)
        self.assertEqual(self.fichiers_televerses(), avant, "le .txt ecrit est retire")

    def test_texte_vide(self):
        self.connecter("remi")
        self.assertEqual(self.tickets.ajouter_texte(1, "   ").motif, "le texte est vide")

    def test_fichier_introuvable(self):
        self.connecter("remi")
        r = self.tickets.joindre_image(1, os.path.join(self.ailleurs.name, "absent.png"))
        self.assertIn("introuvable", r.motif)

    def test_noms_uniques(self):
        self.connecter("remi")
        chemin = self.image()
        self.assertTrue(self.tickets.joindre_image(1, chemin).ok)
        self.assertTrue(self.tickets.joindre_image(1, chemin).ok, "meme image deux fois : deux copies distinctes")
        noms = [n for n in self.fichiers_televerses() if n.endswith(".png") and n != "capture.png"]
        self.assertEqual(len(noms), 2)
        self.assertNotEqual(noms[0], noms[1])
        for nom in noms:
            self.assertRegex(nom, r"^\d{8}_\d{6}_[0-9a-f]{8}\.png$", "date, heure, 8 caracteres aleatoires")


class TestOutils(unittest.TestCase):

    def setUp(self):
        niveau = logging.root.manager.disable  # d'autres modules de test coupent le journal
        logging.disable(logging.NOTSET)
        self.addCleanup(logging.disable, niveau)

    def test_resultat_immuable(self):
        r = Resultat.succes(3, ["note"])
        self.assertEqual((r.ok, r.valeur, r.details), (True, 3, ("note",)))
        with self.assertRaises(AttributeError):
            r.ok = False

    def test_capture_restaure_le_journal(self):
        journal = logging.getLogger("gestion_tickets")
        niveau, gestionnaires = journal.level, list(journal.handlers)
        with CaptureMotif() as c:
            logging.getLogger("gestion_tickets.ticket").info("refus : exemple")
        self.assertEqual(c.motif, "exemple")
        self.assertEqual((journal.level, journal.handlers), (niveau, gestionnaires))

    def test_dossier_d_import(self):
        self.assertEqual(ImportFichiers("televersements").dossier, "televersements")

    def test_capture_vide(self):
        with CaptureMotif() as c:
            pass
        self.assertIsNone(c.motif)
        self.assertEqual(c.motif_ou("defaut"), "defaut")


if __name__ == "__main__":
    unittest.main()
