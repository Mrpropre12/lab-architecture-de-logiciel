"""F6 Ajouter a la description : un texte tape ou une image choisie sur le disque."""
import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QTabWidget,
                               QVBoxLayout, QWidget)

from application import EXTENSIONS_IMAGES

from ..widgets import BandeauResultat, Champ, bouton, etiquette

FILTRE_IMAGES = "Images (" + " ".join("*" + e for e in EXTENSIONS_IMAGES) + ")"


def choisir_image(parent) -> str:
    """Boite de dialogue du systeme (accessible), filtree sur les images acceptees."""
    chemin, _ = QFileDialog.getOpenFileName(parent, "Choisir une image", os.path.expanduser("~"), FILTRE_IMAGES)
    return chemin


def apercu(chemin: str, largeur_max: int = 320) -> QPixmap:
    lecteur = QImageReader(chemin)
    taille = lecteur.size()
    if taille.isValid() and taille.width() > largeur_max:
        lecteur.setScaledSize(QSize(largeur_max, int(taille.height() * largeur_max / taille.width())))
    image = lecteur.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


class DialogueAjout(QDialog):

    def __init__(self, tickets, numero: int, parent=None) -> None:
        super().__init__(parent)
        self.__tickets, self.__numero = tickets, numero
        self.resultat, self.message = None, ""
        self.setWindowTitle(f"Ajouter à la description du ticket {numero}")
        self.setMinimumWidth(520)
        self.bandeau = BandeauResultat()

        # onglet Texte
        self.texte = QPlainTextEdit()
        self.texte.setTabChangesFocus(True)
        self.texte.setMinimumHeight(140)
        self.champ_texte = Champ("&Texte", self.texte, "Étapes pour reproduire, message d'erreur, contexte.")
        page_texte = QWidget()
        QVBoxLayout(page_texte).addWidget(self.champ_texte)

        # onglet Image
        self.chemin = QLineEdit()
        self.chemin.setReadOnly(True)
        self.champ_image = Champ("&Fichier image", self.chemin, "Formats acceptés : .png, .jpg, .gif, 10 Mo au plus.")
        parcourir = bouton("&Parcourir…", "Choisir un fichier image")
        parcourir.clicked.connect(self.parcourir)
        self.vignette = QLabel()
        self.vignette.setAccessibleName("Aperçu de l'image choisie")
        page_image = QWidget()
        c = QVBoxLayout(page_image)
        c.addWidget(self.champ_image)
        c.addWidget(parcourir, 0, Qt.AlignLeft)
        c.addWidget(self.vignette)
        c.addStretch(1)

        self.onglets = QTabWidget()
        self.onglets.setAccessibleName("Type d'ajout : texte ou image")
        self.onglets.addTab(page_texte, "Te&xte")
        self.onglets.addTab(page_image, "&Image")

        ajouter = bouton("&Ajouter", role="principal")
        ajouter.setDefault(True)
        ajouter.clicked.connect(self.ajouter)
        annuler = bouton("Annuler")
        annuler.clicked.connect(self.reject)
        boutons = QHBoxLayout()
        boutons.addWidget(ajouter)
        boutons.addStretch(1)
        boutons.addWidget(annuler)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(20, 16, 20, 16)
        colonne.addWidget(etiquette("Ajoutez un texte ou une image. La vidéo n'est pas prise en charge "
                                    "dans cette version.", "secondaire"))
        colonne.addWidget(self.bandeau)
        colonne.addWidget(self.onglets)
        colonne.addLayout(boutons)
        self.texte.setFocus()

    def parcourir(self) -> None:
        chemin = choisir_image(self)
        if chemin:
            self.choisir(chemin)

    def choisir(self, chemin: str) -> None:
        self.chemin.setText(chemin)
        self.champ_image.effacer_erreur()
        image = apercu(chemin)
        self.vignette.setPixmap(image)
        self.vignette.setAccessibleName(f"Aperçu de {os.path.basename(chemin)}")
        if image.isNull():
            self.vignette.setText("Aperçu impossible : le fichier sera vérifié à l'ajout.")

    def ajouter(self) -> None:
        if self.onglets.currentIndex() == 0:
            if not self.texte.toPlainText().strip():
                self.champ_texte.erreur("le texte est vide")
                self.texte.setFocus()
                return
            r = self.__tickets.ajouter_texte(self.__numero, self.texte.toPlainText())
            message = "texte ajouté à la description"
        else:
            if not self.chemin.text():
                self.champ_image.erreur("choisissez une image")
                return
            r = self.__tickets.joindre_image(self.__numero, self.chemin.text())
            message = f"image {os.path.basename(self.chemin.text())} jointe"
        if not r.ok:
            self.bandeau.refus(r.motif)
            return
        self.resultat, self.message = r, message
        self.accept()
