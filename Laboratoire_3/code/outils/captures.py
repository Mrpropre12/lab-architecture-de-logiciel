"""Captures d'ecran de toutes les fenetres, pour le rapport du labo 3.

Usage, depuis le dossier code :  python outils/captures.py [dossier_de_sortie]
Sans ecran (serveur, integration continue) : QT_QPA_PLATFORM=offscreen python outils/captures.py

Chaque fenetre est ouverte dans un etat representatif, puis enregistree en PNG.
Les donnees sont celles de donnees_demo ; rien n'est ecrit hors d'un dossier temporaire.
"""
import os
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(ICI)
sys.path.insert(0, CODE)
os.environ.setdefault("TICKETS_UPLOAD_DIR", tempfile.mkdtemp(prefix="televersements_"))

from gestion_tickets.acteurs import UserRegistry  # noqa: E402

UserRegistry.PBKDF2_ITERATIONS = 1_000  # demonstration seulement : des captures plus rapides

import donnees_demo  # noqa: E402
from application import Priority, creer_application  # noqa: E402
from interface import theme  # noqa: E402
from interface.app import creer_qapplication  # noqa: E402
from interface.fenetres.aide import FenetreAide  # noqa: E402
from interface.fenetres.ajout import DialogueAjout  # noqa: E402
from interface.fenetres.comptes import DialogueRole, FenetreComptes  # noqa: E402
from interface.fenetres.connexion import FenetreConnexion, FenetreInscription  # noqa: E402
from interface.fenetres.dialogues import (DialogueAssigner, DialogueConfirmation, DialogueMotif,  # noqa: E402
                                          DialoguePriorite, DialogueTitre)
from interface.fenetres.nouveau import FenetreNouveauTicket  # noqa: E402
from interface.fenetres.principale import FenetrePrincipale  # noqa: E402
from interface.fenetres.profil import FenetreProfil  # noqa: E402


def main(sortie: str) -> list:
    os.makedirs(sortie, exist_ok=True)
    app = creer_qapplication([])
    users, tickets = donnees_demo.creer_systeme()
    _, comptes, services = creer_application(users, tickets, donnees_demo.TELEVERSEMENTS)
    taille = theme.TailleDuTexte(app)
    faites = []

    def capturer(fenetre, nom, largeur=None, hauteur=None):
        if largeur:
            fenetre.resize(largeur, hauteur or fenetre.height())
        fenetre.show()
        app.processEvents()
        if largeur is None:
            fenetre.adjustSize()
            app.processEvents()
        chemin = os.path.join(sortie, f"{nom}.png")
        fenetre.grab().save(chemin)
        faites.append(chemin)
        fenetre.hide()

    def connecter(prenom):
        comptes.deconnecter()
        assert comptes.connecter(f"{prenom}@uqac.ca", f"{prenom}-2026").ok

    image = os.path.join(tempfile.mkdtemp(), "capture_ecran.png")
    with open(image, "wb") as f:
        f.write(donnees_demo.png(480, 270, (15, 98, 254)))

    # F1 et F2
    f1 = FenetreConnexion(comptes, donnees_demo.COMPTES_DEMO)
    capturer(f1, "F1a_connexion")
    f1.courriel.setText("alice@uqac.ca")
    f1.mot_de_passe.setText("mauvais-mdp")
    f1.connecter()
    capturer(f1, "F1b_connexion_refusee")
    f1.bouton_demo.setChecked(True)
    capturer(f1, "F1c_comptes_de_demonstration")
    f2 = FenetreInscription(comptes)
    f2.nom.setText("Zoé")
    f2.courriel.setText("zoe@uqac.ca")
    f2.mot_de_passe.setText("une phrase de passe")
    f2.confirmation.setText("une phrase de pase")
    f2.valider()
    capturer(f2, "F2_creer_un_compte_erreur")

    # F3 selon les roles
    connecter("remi")
    capturer(FenetrePrincipale(comptes, services, taille, donnees_demo.COMPTES_DEMO), "F3a_principale_rapporteur",
             1000, 520)
    connecter("diane")
    f3 = FenetrePrincipale(comptes, services, taille, donnees_demo.COMPTES_DEMO)
    f3.filtre.setCurrentIndex(f3.filtre.findData("tous"))
    capturer(f3, "F3b_principale_developpeuse_tous", 1000, 520)

    # F4 : assigne, puis validation, refus
    connecter("damien")
    f3 = FenetrePrincipale(comptes, services, taille, donnees_demo.COMPTES_DEMO)
    f3.ouvrir_ticket(1)
    detail = f3._FenetrePrincipale__details[1]
    capturer(detail, "F4a_detail_assigne", 940, 720)
    services.soumettre(1)
    detail.charger()
    detail.bandeau.afficher(services.valider(1), "")  # vrai refus du modele : l'assigne valide son travail
    capturer(detail, "F4b_detail_validation_refus", 940, 720)

    # F5 nouveau ticket
    connecter("rita")
    f5 = FenetreNouveauTicket(services)
    f5.titre.setText("Le bouton Envoyer est invisible au clavier")
    f5.priorite.setCurrentIndex(list(Priority).index(Priority.HAUTE))
    f5.texte.setPlainText("1. Ouvrir le formulaire\n2. Appuyer sur Tab\n3. Le focus saute le bouton Envoyer")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem
    item = QListWidgetItem("capture_ecran.png")
    item.setData(Qt.UserRole, image)
    f5.images.addItem(item)
    capturer(f5, "F5_nouveau_ticket")
    f5.creer()
    numero = f5.resultat.valeur

    # F6 ajout : texte puis image
    f6 = DialogueAjout(services, numero)
    f6.texte.setPlainText("Constaté aussi avec NVDA : le bouton n'est jamais annoncé.")
    capturer(f6, "F6a_ajout_texte")
    f6.onglets.setCurrentIndex(1)
    f6.choisir(image)
    capturer(f6, "F6b_ajout_image")

    f3 = FenetrePrincipale(comptes, services, taille, donnees_demo.COMPTES_DEMO)
    f3.ouvrir_ticket(numero)
    capturer(f3._FenetrePrincipale__details[numero], "F4c_detail_texte_et_image", 940, 760)

    # F7 dialogues d'action
    connecter("diane")
    capturer(DialogueMotif("Rejeter le travail", "&Rejeter"), "F7a_motif_rejet")
    capturer(DialogueAssigner(services.assignables().valeur, "Damien"), "F7b_assigner")
    capturer(DialogueTitre("Faute dans le menu Aide"), "F7c_modifier_titre")
    capturer(DialoguePriorite(Priority.BASSE), "F7d_priorite")
    capturer(DialogueConfirmation("Archiver le ticket", "Archiver le ticket 1 ? L'archivage est définitif : le "
                                  "ticket restera consultable, mais plus aucune modification ne sera possible.",
                                  "&Archiver"), "F7e_confirmation_archivage")

    # Parcours jusqu'a l'archive, vu par l'administratrice
    services.valider(1)
    connecter("alice")
    services.archiver(1)
    f3 = FenetrePrincipale(comptes, services, taille, donnees_demo.COMPTES_DEMO)
    f3.onglets.setCurrentIndex(1)
    capturer(f3, "F3c_principale_archives", 1000, 520)
    f3.ouvrir_ticket(1)
    capturer(f3._FenetrePrincipale__details[1], "F4d_detail_archive_lecture_seule", 940, 720)

    # F8, F9, F10
    f8 = FenetreComptes(comptes)
    capturer(f8, "F8a_gestion_des_comptes", 720, 460)
    capturer(DialogueRole("Attribuer un rôle", "Remi", ["Developpeur", "Administrateur"], "&Attribuer"),
             "F8b_attribuer_un_role")
    capturer(FenetreProfil(comptes.profil().valeur), "F9_profil")
    capturer(FenetreAide(donnees_demo.COMPTES_DEMO), "F10_aide_et_accessibilite", 680, 900)

    # Texte a 200 % (WCAG 1.4.4)
    taille.regler(200)
    f3 = FenetrePrincipale(comptes, services, taille, donnees_demo.COMPTES_DEMO)
    f3.filtre.setCurrentIndex(f3.filtre.findData("tous"))
    capturer(f3, "W1_principale_texte_200", 1280, 720)
    f3.ouvrir_ticket(2)
    capturer(f3._FenetrePrincipale__details[2], "W2_detail_texte_200", 1280, 900)
    taille.regler(100)
    return faites


if __name__ == "__main__":
    dossier = sys.argv[1] if len(sys.argv) > 1 else os.path.join(CODE, "docs", "captures")
    for chemin in main(dossier):
        print(chemin)
