"""F5 Nouveau ticket : titre, priorite, texte de description et images, en une seule fois."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QVBoxLayout)

from application import Priority

from .. import theme
from ..widgets import BandeauResultat, Champ, bouton
from .ajout import choisir_image


class FenetreNouveauTicket(QDialog):

    def __init__(self, tickets, parent=None) -> None:
        super().__init__(parent)
        self.__tickets = tickets
        self.resultat = None
        self.setWindowTitle("Nouveau ticket")
        self.setMinimumWidth(560)
        self.bandeau = BandeauResultat()

        self.titre = QLineEdit()
        self.titre.setMaxLength(200)
        self.champ_titre = Champ("&Titre", self.titre, "Une phrase courte qui résume le problème (200 caractères "
                                 "au plus).", obligatoire=True)
        self.priorite = QComboBox()
        for p in Priority:
            self.priorite.addItem(theme.PRIORITES[p][0], p)
        self.priorite.setCurrentIndex(list(Priority).index(Priority.NORMALE))
        self.texte = QPlainTextEdit()
        self.texte.setTabChangesFocus(True)
        self.texte.setMinimumHeight(110)
        self.images = QListWidget()
        self.images.setMaximumHeight(110)
        ajouter = bouton("Ajouter une &image…")
        ajouter.clicked.connect(self.ajouter_image)
        self.retirer = bouton("&Retirer l'image sélectionnée")
        self.retirer.clicked.connect(self.retirer_image)
        self.retirer.setEnabled(False)
        self.images.currentRowChanged.connect(lambda i: self.retirer.setEnabled(i >= 0))
        boutons_images = QHBoxLayout()
        boutons_images.addWidget(ajouter)
        boutons_images.addWidget(self.retirer)
        boutons_images.addStretch(1)

        creer = bouton("&Créer le ticket", role="principal")
        creer.setDefault(True)
        creer.clicked.connect(self.creer)
        annuler = bouton("Annuler")
        annuler.clicked.connect(self.reject)
        boutons = QHBoxLayout()
        boutons.addWidget(creer)
        boutons.addStretch(1)
        boutons.addWidget(annuler)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(20, 16, 20, 16)
        colonne.setSpacing(10)
        colonne.addWidget(self.bandeau)
        colonne.addWidget(self.champ_titre)
        colonne.addWidget(Champ("&Priorité", self.priorite))
        colonne.addWidget(Champ("&Description", self.texte, "Facultatif. Vous pourrez compléter plus tard."))
        colonne.addWidget(Champ("Ima&ges jointes", self.images, ".png, .jpg ou .gif, 10 Mo au plus chacune."))
        colonne.addLayout(boutons_images)
        colonne.addLayout(boutons)
        self.titre.setFocus()

    def ajouter_image(self) -> None:
        chemin = choisir_image(self)
        if chemin:
            item = QListWidgetItem(os.path.basename(chemin))
            item.setData(Qt.UserRole, chemin)
            item.setToolTip(chemin)
            self.images.addItem(item)
            self.images.setCurrentItem(item)

    def retirer_image(self) -> None:
        ligne = self.images.currentRow()
        if ligne >= 0:
            self.images.takeItem(ligne)

    def chemins_images(self):
        return [self.images.item(i).data(Qt.UserRole) for i in range(self.images.count())]

    def creer(self) -> None:
        self.champ_titre.effacer_erreur()
        if not self.titre.text().strip():
            self.champ_titre.erreur("le titre est obligatoire")
            self.bandeau.refus("le titre est obligatoire")
            self.titre.setFocus()
            return
        r = self.__tickets.creer(self.titre.text(), self.priorite.currentData(), self.texte.toPlainText(),
                                 self.chemins_images())
        if not r.ok:
            self.bandeau.refus(r.motif)
            return
        self.resultat = r
        self.accept()
