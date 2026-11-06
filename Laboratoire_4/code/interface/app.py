"""Point d'entree de l'interface : connexion (F1), puis fenetre principale (F3), en boucle
tant que l'utilisateur se deconnecte au lieu de quitter.

Labo 4 : les services recus peuvent etre locaux (application) ou distants (client). Avec un
client distant, le serveur est reveille avant F1, sans figer l'ecran.
"""
import sys
import threading

from PySide6.QtCore import QEventLoop, QLocale, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QProgressDialog

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


def reveiller_serveur(comptes, parent=None):
    """Client distant seulement : appelle comptes.reveiller() dans un autre fil.

    Un service Render gratuit endormi met environ une minute a repondre. La boucle d'evenements
    continue de tourner (l'ecran reste vivant) ; une fenetre d'attente apparait si l'attente
    depasse une demi-seconde. Renvoie le Resultat ; un echec est signale sans bloquer : la
    connexion pourra etre retentee depuis F1."""
    resultat = {}
    fil = threading.Thread(target=lambda: resultat.update(r=comptes.reveiller()), daemon=True)
    attente = QProgressDialog("Réveil du serveur… jusqu'à une minute si le service dormait.", None, 0, 0, parent)
    attente.setWindowTitle("Connexion au serveur")
    attente.setAccessibleName("Réveil du serveur en cours")
    attente.setMinimumDuration(0)
    attente.reset()  # n'apparait que si l'attente dure
    boucle, minuterie = QEventLoop(), QTimer()
    minuterie.timeout.connect(lambda: None if fil.is_alive() else boucle.quit())
    fil.start()
    QTimer.singleShot(500, lambda: fil.is_alive() and attente.show())
    minuterie.start(100)
    boucle.exec()
    minuterie.stop()
    attente.close()
    r = resultat["r"]
    if not r.ok:
        QMessageBox.warning(parent, "Serveur injoignable",
                            f"{r.motif}\n\nVous pourrez réessayer depuis la fenêtre de connexion.")
    return r


def lancer(comptes, tickets, comptes_demo=(), argv=None) -> int:
    """comptes, tickets : services locaux (application) ou distants (client), memes methodes.
    comptes_demo : aide a la demonstration."""
    app = creer_qapplication(argv)
    taille = theme.TailleDuTexte(app)
    if hasattr(comptes, "reveiller"):
        reveiller_serveur(comptes)
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
