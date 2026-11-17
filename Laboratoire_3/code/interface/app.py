"""Point d'entree de l'interface : connexion (F1), puis fenetre principale (F3), en boucle
tant que l'utilisateur se deconnecte au lieu de quitter."""
import sys

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication, QDialog

from . import theme
from .fenetres.connexion import FenetreConnexion
from .fenetres.principale import FenetrePrincipale


def creer_qapplication(argv=None) -> QApplication:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Gestionnaire de tickets")
    app.setApplicationDisplayName("Gestionnaire de tickets")
    QLocale.setDefault(QLocale(QLocale.French, QLocale.Canada))  # langue de l'interface (WCAG 3.1.1)
    theme.appliquer(app)
    return app


def lancer(comptes, tickets, comptes_demo=(), argv=None) -> int:
    """comptes, tickets : services de la couche application. comptes_demo : aide a la demonstration."""
    app = creer_qapplication(argv)
    taille = theme.TailleDuTexte(app)
    while True:
        connexion = FenetreConnexion(comptes, comptes_demo)
        if connexion.exec() != QDialog.Accepted:
            return 0
        principale = FenetrePrincipale(comptes, tickets, taille, comptes_demo)
        etat = {"deconnexion": False}
        principale.deconnexion.connect(lambda: etat.update(deconnexion=True))
        principale.show()
        app.exec()
        if not etat["deconnexion"]:
            return 0
