"""DescriptionVisitor : la description d'un ticket en blocs, pour l'interface graphique."""
import dataclasses
import os
import sys
import tempfile
import unittest
from unittest import mock

from aide import MDP
from gestion_tickets.acteurs import DeveloperRole, UserRegistry
from gestion_tickets.consultation import (BlocCommentaire, BlocImage, BlocTexte, BlocTicket, BlocVideo,
                                          DescriptionVisitor, ScreenRenderVisitor)
from gestion_tickets.ticket import ContentFactory, Priority, TicketRegistry, ViewVisitor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
from donnees_demo import png  # noqa: E402


class TestDescriptionVisitor(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        fichiers = {"etapes.txt": "1. Ouvrir le portail\n2. Ecran noir".encode("utf-8"),
                    "capture.png": png(64, 48, (10, 20, 30)),
                    "demo.mp4": b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64}
        for nom, donnees in fichiers.items():
            with open(os.path.join(self.dossier.name, nom), "wb") as f:
                f.write(donnees)
        patch = mock.patch.object(ContentFactory, "_ContentFactory__UPLOAD_DIR", self.dossier.name)
        patch.start()
        self.addCleanup(patch.stop)
        self.users = UserRegistry("Alice", "alice@uqac.ca", MDP)
        self.alice = self.users.authenticate("alice@uqac.ca", MDP)
        self.remi = self.users.register("Remi", "remi@uqac.ca", MDP)
        self.rita = self.users.register("Rita", "rita@uqac.ca", MDP)
        self.damien = self.users.register("Damien", "damien@uqac.ca", MDP)
        self.users.grant_role(self.alice, self.damien, DeveloperRole())
        self.tickets = TicketRegistry(self.users)
        self.t = self.tickets.create(self.remi, "Ecran noir", Priority.HAUTE)
        for nom in ("etapes.txt", "capture.png", "demo.mp4"):
            self.assertTrue(self.t.add_content(self.remi, ContentFactory.from_path(nom)))
        self.t.add_comment(self.remi, "Arrive a chaque redemarrage.")
        self.t.assign(self.alice, self.damien)

    def test_est_un_view_visitor(self):
        self.assertIsInstance(DescriptionVisitor(), ViewVisitor)

    def test_blocs_dans_l_ordre_du_parcours(self):
        v = DescriptionVisitor()
        self.assertTrue(self.t.consult(self.remi, v))
        self.assertEqual([type(b) for b in v.blocks()],
                         [BlocTicket, BlocTexte, BlocImage, BlocVideo, BlocCommentaire])

    def test_contenu_des_blocs(self):
        v = DescriptionVisitor()
        self.t.consult(self.remi, v)
        ticket, texte, image, video, commentaire = v.blocks()
        self.assertEqual((ticket.numero, ticket.titre, ticket.statut, ticket.priorite, ticket.auteur, ticket.assigne),
                         (1, "Ecran noir", "ASSIGNE", "HAUTE", "Remi", "Damien"))
        self.assertIsNone(ticket.archive_le)
        self.assertEqual((texte.nom, texte.texte), ("etapes.txt", "1. Ouvrir le portail\n2. Ecran noir"))
        self.assertEqual((image.nom, image.largeur, image.hauteur), ("capture.png", 64, 48))
        self.assertTrue(os.path.isfile(image.chemin))
        self.assertEqual(image.texte_de_remplacement, "Image capture.png, 64 × 48 pixels")
        self.assertEqual(video.nom, "demo.mp4")
        self.assertEqual((commentaire.numero, commentaire.auteur, commentaire.texte),
                         (1, "Remi", "Arrive a chaque redemarrage."))

    def test_image_illisible(self):
        """Signature PNG valide mais fichier tronque : jointe, mais ses dimensions sont illisibles."""
        with open(os.path.join(self.dossier.name, "abime.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")
        t = self.tickets.create(self.remi, "Image abimee", Priority.BASSE)
        self.assertTrue(t.add_content(self.remi, ContentFactory.from_path("abime.png")))
        v = DescriptionVisitor()
        t.consult(self.remi, v)
        image = v.blocks()[1]
        self.assertFalse(image.lisible)
        self.assertEqual(image.texte_de_remplacement, "Image abime.png, illisible")

    def test_version_texte(self):
        v = DescriptionVisitor()
        self.t.consult(self.remi, v)
        texte = v.result()
        for attendu in ("Ticket 1 : Ecran noir", "Statut ASSIGNE, priorite HAUTE", "Auteur Remi, assigne Damien",
                        "Texte etapes.txt :", "Image capture.png, 64 × 48 pixels",
                        "Video demo.mp4, non prise en charge", "Commentaire 1 de Remi"):
            self.assertIn(attendu, texte)
        commentaire = v.blocks()[-1]
        self.assertIn(f"Commentaire 1 de Remi, {commentaire.publie_le:%Y-%m-%d %H:%M} : Arrive", texte)

    def test_nouveau_parcours_repart_de_zero(self):
        v = DescriptionVisitor()
        self.t.consult(self.remi, v)
        self.t.consult(self.remi, v)
        self.assertEqual(len(v.blocks()), 5)

    def test_refus_ne_produit_aucun_bloc(self):
        v = DescriptionVisitor()
        self.assertFalse(self.t.consult(self.rita, v), "ticket invisible pour Rita")
        self.assertEqual(v.blocks(), ())
        self.assertEqual(v.result(), "")

    def test_blocs_immuables(self):
        v = DescriptionVisitor()
        self.t.consult(self.remi, v)
        for b in v.blocks():
            champ = dataclasses.fields(b)[0].name
            with self.subTest(bloc=type(b).__name__), self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(b, champ, "pirate")
        self.assertIsInstance(v.blocks(), tuple)

    def test_ticket_inchange_par_ce_visiteur(self):
        """Patron Visiteur : ajouter ce visiteur n'a demande aucune modification de Ticket."""
        avant, apres = ScreenRenderVisitor(), ScreenRenderVisitor()
        self.t.consult(self.remi, avant)
        self.t.consult(self.remi, DescriptionVisitor())
        self.t.consult(self.remi, apres)
        self.assertEqual(avant.result(), apres.result())


if __name__ == "__main__":
    unittest.main()
