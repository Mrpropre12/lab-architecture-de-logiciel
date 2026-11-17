"""Interface graphique : tests de fumee et verifications d'accessibilite automatisables.

Plateforme Qt « offscreen » : aucun ecran necessaire. Les verifications manuelles
(NVDA, Narrateur, FastPass, contraste mesure a l'ecran) restent au protocole WCAG.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAccessible
    from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QWidget
except ImportError:  # PySide6 absent : l'interface n'est pas testee
    QApplication = None

import aide  # noqa: F401
from gestion_tickets.ticket import ContentFactory

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
import donnees_demo  # noqa: E402


def nom_accessible(w) -> str:
    interface = QAccessible.queryAccessibleInterface(w)
    return interface.text(QAccessible.Name) if interface else ""


def focalisables(fenetre):
    return [w for w in fenetre.findChildren(QWidget)
            if w.isVisibleTo(fenetre) and w.isEnabled() and w.focusPolicy() & Qt.TabFocus]


@unittest.skipIf(QApplication is None, "PySide6 non installe")
class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from interface.app import creer_qapplication
        cls.app = creer_qapplication([])

    def setUp(self):
        from application import creer_application
        from interface import theme
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        for cible, attribut in ((ContentFactory, "_ContentFactory__UPLOAD_DIR"), (donnees_demo, "TELEVERSEMENTS")):
            p = mock.patch.object(cible, attribut, self.dossier.name)
            p.start()
            self.addCleanup(p.stop)
        with mock.patch("builtins.print"):
            users, tickets = donnees_demo.creer_systeme()
        self.session, self.comptes, self.tickets = creer_application(users, tickets, self.dossier.name)
        self.taille = theme.TailleDuTexte(self.app)
        self.addCleanup(self.taille.regler, 100)

    def connecter(self, prenom):
        self.comptes.deconnecter()
        self.assertTrue(self.comptes.connecter(f"{prenom}@uqac.ca", f"{prenom}-2026").ok)

    def principale(self):
        from interface.fenetres.principale import FenetrePrincipale
        f = FenetrePrincipale(self.comptes, self.tickets, self.taille, donnees_demo.COMPTES_DEMO)
        f.show()
        self.addCleanup(f.close)
        return f

    def verifier_noms(self, fenetre):
        """WCAG 4.1.2 : chaque controle atteignable au clavier a un nom pour le lecteur d'ecran."""
        fenetre.show()
        self.app.processEvents()
        for w in focalisables(fenetre):
            with self.subTest(fenetre=fenetre.windowTitle(), widget=type(w).__name__):
                self.assertTrue(nom_accessible(w).strip(), f"{type(w).__name__} sans nom accessible")

    def verifier_cibles(self, fenetre):
        """WCAG 2.5.8 : boutons d'au moins 24 px (32 px vises)."""
        fenetre.show()
        self.app.processEvents()
        for b in fenetre.findChildren(QAbstractButton):
            if b.isVisibleTo(fenetre) and b.text():
                with self.subTest(bouton=b.text()):
                    self.assertGreaterEqual(b.height(), 24)


class TestConnexion(Base):

    def fenetre(self):
        from interface.fenetres.connexion import FenetreConnexion
        f = FenetreConnexion(self.comptes, donnees_demo.COMPTES_DEMO)
        self.addCleanup(f.close)
        return f

    def test_connexion_reussie(self):
        f = self.fenetre()
        f.courriel.setText("remi@uqac.ca")
        f.mot_de_passe.setText("remi-2026")
        f.bouton_connecter.click()
        self.assertEqual(f.result(), QDialog.Accepted)
        self.assertEqual(self.session.connecte.name, "Remi")

    def test_connexion_refusee_affiche_le_motif(self):
        f = self.fenetre()
        f.courriel.setText("remi@uqac.ca")
        f.mot_de_passe.setText("mauvais-mdp")
        f.bouton_connecter.click()
        self.assertIn("REFUSÉ : courriel ou mot de passe incorrect", f.bandeau.texte)
        self.assertEqual(f.mot_de_passe.text(), "", "le mot de passe est efface")

    def test_champs_vides_signales_sous_le_champ(self):
        f = self.fenetre()
        f.show()
        f.bouton_connecter.click()
        self.assertIn("Erreur", f.champ_courriel.message_erreur)
        self.assertTrue(f.courriel.hasFocus() or not f.isActiveWindow())

    def test_mot_de_passe_masque_mais_affichable(self):
        from PySide6.QtWidgets import QLineEdit
        f = self.fenetre()
        self.assertEqual(f.mot_de_passe.echoMode(), QLineEdit.Password)
        f.afficher_mdp.setChecked(True)
        self.assertEqual(f.mot_de_passe.echoMode(), QLineEdit.Normal)

    def test_comptes_de_demonstration_remplissent_le_formulaire(self):
        f = self.fenetre()
        f.bouton_demo.setChecked(True)
        f.tableau_demo.cellActivated.emit(3, 0)
        self.assertEqual((f.courriel.text(), f.mot_de_passe.text()), ("diane@uqac.ca", "diane-2026"))

    def test_ordre_de_tabulation(self):
        f = self.fenetre()
        f.show()
        self.app.processEvents()
        attendu = [f.courriel, f.mot_de_passe, f.afficher_mdp, f.bouton_connecter, f.bouton_inscrire,
                   f.bouton_quitter, f.bouton_demo]
        w, vus = f.courriel, []
        for _ in attendu:
            vus.append(w)
            w = w.nextInFocusChain()
            while not (w.focusPolicy() & Qt.TabFocus and w.isVisibleTo(f) and w.isEnabled()):
                w = w.nextInFocusChain()
        self.assertEqual(vus, attendu)

    def test_noms_et_cibles(self):
        f = self.fenetre()
        f.bouton_demo.setChecked(True)
        self.verifier_noms(f)
        self.verifier_cibles(f)

    def test_inscription(self):
        from interface.fenetres.connexion import FenetreInscription
        f = FenetreInscription(self.comptes)
        self.addCleanup(f.close)
        self.verifier_noms(f)
        f.nom.setText("Zoé")
        f.courriel.setText("zoe@uqac.ca")
        f.mot_de_passe.setText("une phrase de passe")
        f.confirmation.setText("une autre phrase")
        f.valider()
        self.assertIn("identiques", f.bandeau.texte)
        f.confirmation.setText("une phrase de passe")
        f.valider()
        self.assertEqual(f.result(), QDialog.Accepted)


class TestPrincipaleEtDetail(Base):

    def test_menus_selon_le_role(self):
        self.connecter("remi")
        f = self.principale()
        filtres = [f.filtre.itemData(i) for i in range(f.filtre.count())]
        self.assertNotIn("tous", filtres, "VIEW_ALL absent pour un rapporteur")
        menus = [a.text() for a in f.menuBar().actions()]
        self.assertEqual(menus, ["&Ticket", "&Comptes", "A&ffichage", "&Aide"])
        comptes = f.menuBar().actions()[1].menu().actions()
        self.assertEqual([a.text() for a in comptes], ["Mon &profil"])

    def test_liste_et_filtres(self):
        self.connecter("diane")
        f = self.principale()
        f.filtre.setCurrentIndex(f.filtre.findData("tous"))
        self.assertEqual(f.modele_actifs.rowCount(), 2)
        f.statut.setCurrentIndex(f.statut.findText("OUVERT"))
        self.assertEqual(f.modele_actifs.rowCount(), 1)
        self.assertEqual(f.modele_actifs.item(0, 2).text(), "OUVERT")
        self.verifier_noms(f)

    def test_detail_boutons_selon_allowed_actions(self):
        self.connecter("damien")
        f = self.principale()
        f.ouvrir_ticket(1)
        d = f._FenetrePrincipale__details[1]
        permises = self.tickets.actions_permises(1)
        for permission, b in d.boutons.items():
            with self.subTest(permission=permission.value):
                self.assertEqual(b.isEnabled(), permission in permises)
        self.assertIn("soumettre", d.possibles.text())
        self.verifier_noms(d)
        self.verifier_cibles(d)

    def test_action_puis_rafraichissement(self):
        self.connecter("damien")
        f = self.principale()
        f.ouvrir_ticket(1)
        d = f._FenetrePrincipale__details[1]
        d.agir(next(p for p in d.boutons if p.value == "SUBMIT"))
        self.assertIn("OK : travail soumis", d.bandeau.texte)
        self.assertEqual(d.pastille_statut.libelle, "VALIDATION")
        self.assertEqual(f.modele_actifs.item(0, 2).text(), "VALIDATION", "liste principale rafraichie")

    def test_image_avec_texte_de_remplacement(self):
        self.connecter("remi")
        f = self.principale()
        f.ouvrir_ticket(1)
        d = f._FenetrePrincipale__details[1]
        noms = [nom_accessible(w) for w in d.findChildren(QWidget)]
        self.assertIn("Image capture.png, 320 × 180 pixels", noms)

    def test_texte_saisi_affiche_en_texte_brut(self):
        """Un titre contenant du HTML s'affiche tel quel, sans etre interprete."""
        self.connecter("rita")
        r = self.tickets.creer("<b>gras</b> <a href='x'>lien</a>", self.tickets_priorite())
        f = self.principale()
        f.ouvrir_ticket(r.valeur)
        d = f._FenetrePrincipale__details[r.valeur]
        self.assertEqual(d.titre.textFormat(), Qt.PlainText)
        self.assertIn("<b>gras</b>", d.titre.text())

    def tickets_priorite(self):
        from application import Priority
        return Priority.BASSE

    def test_taille_du_texte_200(self):
        self.connecter("remi")
        avant = self.app.font().pointSizeF()
        self.taille.regler(200)
        self.assertAlmostEqual(self.app.font().pointSizeF(), avant * 2, delta=0.6)
        self.taille.regler(100)
        self.assertAlmostEqual(self.app.font().pointSizeF(), avant, delta=0.6)


class TestAutresFenetres(Base):

    def test_toutes_les_fenetres_s_ouvrent_avec_des_noms(self):
        from application import Priority
        from interface.fenetres.aide import FenetreAide
        from interface.fenetres.ajout import DialogueAjout
        from interface.fenetres.comptes import FenetreComptes
        from interface.fenetres.dialogues import (DialogueAssigner, DialogueConfirmation, DialogueMotif,
                                                  DialoguePriorite, DialogueTitre)
        from interface.fenetres.nouveau import FenetreNouveauTicket
        from interface.fenetres.profil import FenetreProfil
        self.connecter("alice")
        fenetres = [FenetreNouveauTicket(self.tickets), DialogueAjout(self.tickets, 1),
                    DialogueMotif("Rejeter", "&Rejeter"), DialogueAssigner(self.tickets.assignables().valeur, None),
                    DialogueTitre("Titre"), DialoguePriorite(Priority.BASSE),
                    DialogueConfirmation("Archiver", "Sur ?", "&Archiver"), FenetreComptes(self.comptes),
                    FenetreProfil(self.comptes.profil().valeur), FenetreAide(donnees_demo.COMPTES_DEMO)]
        for f in fenetres:
            self.addCleanup(f.close)
            self.verifier_noms(f)
            self.verifier_cibles(f)

    def test_confirmation_annuler_par_defaut(self):
        from interface.fenetres.dialogues import DialogueConfirmation
        d = DialogueConfirmation("Archiver", "Sur ?", "&Archiver")
        self.addCleanup(d.close)
        self.assertTrue(d.annuler.isDefault())
        self.assertFalse(d.ok.isDefault())

    def test_nouveau_ticket_avec_image(self):
        from interface.fenetres.nouveau import FenetreNouveauTicket
        from PySide6.QtWidgets import QListWidgetItem
        self.connecter("rita")
        image = os.path.join(self.dossier.name, "..", os.path.basename(self.dossier.name) + "_img.png")
        with open(image, "wb") as fichier:
            fichier.write(donnees_demo.png(20, 10, (1, 2, 3)))
        self.addCleanup(os.remove, image)
        f = FenetreNouveauTicket(self.tickets)
        self.addCleanup(f.close)
        f.titre.setText("Avec image")
        f.texte.setPlainText("Description")
        item = QListWidgetItem("img.png")
        item.setData(Qt.UserRole, image)
        f.images.addItem(item)
        f.creer()
        self.assertTrue(f.resultat.ok)
        self.assertEqual(f.resultat.details, ())

    def test_gestion_des_comptes(self):
        from interface.fenetres.comptes import FenetreComptes
        self.connecter("alice")
        f = FenetreComptes(self.comptes)
        self.addCleanup(f.close)
        self.assertEqual(f.tableau.rowCount(), 5)
        self.assertEqual(f.tableau.item(3, 2).text(), "Rapporteur, Développeur")


@unittest.skipIf(QApplication is None, "PySide6 non installe")
class TestTheme(unittest.TestCase):

    def test_contraste_eleve_garde_le_systeme(self):
        from interface import theme
        app = QApplication.instance() or QApplication([])
        feuille = app.styleSheet()
        with mock.patch.object(theme, "contraste_eleve", return_value=True):
            self.assertFalse(theme.appliquer(app))
        self.assertEqual(app.styleSheet(), feuille, "aucune couleur a nous en contraste eleve")

    def test_contrastes_des_jetons(self):
        """Les paires texte et fond du theme respectent WCAG 1.4.3 et 1.4.11."""
        from interface import theme

        def lum(h):
            def c(v):
                v /= 255
                return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
            r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
            return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)

        def rapport(a, b):
            la, lb = sorted((lum(a), lum(b)), reverse=True)
            return (la + 0.05) / (lb + 0.05)

        textes = [theme.TEXTE, theme.TEXTE_SECONDAIRE, theme.GRIS_MINIMAL, theme.ACCENT, theme.INFORMATION,
                  theme.SUCCES, theme.ERREUR, theme.AVERTISSEMENT_TEXTE]
        for t in textes:
            with self.subTest(texte=t):
                self.assertGreaterEqual(rapport(t, theme.FOND), 4.5)
        for valeurs in list(theme.STATUTS.values()) + list(theme.PRIORITES.values()):
            _, fond, texte, _ = valeurs
            with self.subTest(pastille=valeurs[0]):
                self.assertGreaterEqual(rapport(texte, fond), 4.5)
        for fond in (theme.FOND_SUCCES, theme.FOND_ERREUR, theme.FOND_INFO, theme.FOND_ZONE):
            self.assertGreaterEqual(rapport(theme.TEXTE, fond), 4.5)
        self.assertGreaterEqual(rapport(theme.ACCENT, theme.FOND), 3.0, "focus (1.4.11)")
        self.assertGreaterEqual(rapport(theme.GRIS_MINIMAL, theme.FOND), 3.0, "bordures (1.4.11)")


if __name__ == "__main__":
    unittest.main()
