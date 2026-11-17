"""F8 Gestion des comptes (MANAGE_USERS) : roles, desactivation, reactivation."""
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from application import ROLES

from ..libelles import ROLES_AFFICHES
from ..libelles import roles as roles_affiches

from ..widgets import BandeauResultat, Champ, bouton, etiquette
from .dialogues import DialogueConfirmation, _Dialogue


class DialogueRole(_Dialogue):

    def __init__(self, titre: str, nom: str, roles, texte_ok: str, parent=None) -> None:
        super().__init__(titre, f"Compte : {nom}.", texte_ok, parent)
        self.liste = QComboBox()
        for r in roles:
            self.liste.addItem(ROLES_AFFICHES.get(r, r), r)
        self.terminer(Champ("&Rôle", self.liste))
        self.liste.setFocus()

    @property
    def role(self) -> str:
        return self.liste.currentData()


class FenetreComptes(QDialog):

    def __init__(self, comptes, parent=None) -> None:
        super().__init__(parent)
        self.__comptes = comptes
        self.setWindowTitle("Gestion des comptes")
        self.resize(680, 440)
        self.bandeau = BandeauResultat()
        self.tableau = QTableWidget(0, 4)
        self.tableau.setAccessibleName("Comptes")
        self.tableau.setHorizontalHeaderLabels(["N°", "Nom", "Rôles", "État"])
        self.tableau.verticalHeader().hide()
        self.tableau.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableau.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableau.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tableau.setTabKeyNavigation(False)
        self.tableau.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tableau.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tableau.currentCellChanged.connect(lambda *_: self.__boutons())

        self.attribuer = bouton("&Attribuer un rôle…")
        self.retirer = bouton("&Retirer un rôle…")
        self.desactiver = bouton("&Désactiver…", role="danger")
        self.reactiver = bouton("R&éactiver")
        fermer = bouton("Fermer la fe&nêtre")
        self.attribuer.clicked.connect(lambda: self.__role(True))
        self.retirer.clicked.connect(lambda: self.__role(False))
        self.desactiver.clicked.connect(self.__desactiver)
        self.reactiver.clicked.connect(self.__reactiver)
        fermer.clicked.connect(self.accept)
        boutons = QHBoxLayout()
        for b in (self.attribuer, self.retirer, self.desactiver, self.reactiver):
            boutons.addWidget(b)
        boutons.addStretch(1)
        boutons.addWidget(fermer)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(16, 12, 16, 12)
        colonne.addWidget(etiquette("Le système refuse de retirer le rôle Rapporteur, de retirer le rôle "
                                    "Développeur d'un administrateur et de désactiver le dernier administrateur "
                                    "actif.", "secondaire"))
        colonne.addWidget(self.bandeau)
        colonne.addWidget(self.tableau, 1)
        colonne.addLayout(boutons)
        self.actualiser()
        self.tableau.setFocus()

    def actualiser(self) -> None:
        ligne_avant = max(self.tableau.currentRow(), 0)
        r = self.__comptes.lister()
        if not r.ok:
            self.bandeau.refus(r.motif)
            self.liste = []
        else:
            self.liste = r.valeur
        self.tableau.setRowCount(len(self.liste))
        for i, c in enumerate(self.liste):
            for j, v in enumerate((str(c.numero), c.nom, roles_affiches(c.roles), "actif" if c.actif else "désactivé")):
                self.tableau.setItem(i, j, QTableWidgetItem(v))
        if self.liste:
            self.tableau.setCurrentCell(min(ligne_avant, len(self.liste) - 1), 0)
        self.__boutons()

    def __choisi(self):
        i = self.tableau.currentRow()
        return self.liste[i] if 0 <= i < len(self.liste) else None

    def __boutons(self) -> None:
        c = self.__choisi()
        for b in (self.attribuer, self.retirer, self.desactiver, self.reactiver):
            b.setEnabled(c is not None)
        if c:
            self.desactiver.setEnabled(c.actif)
            self.reactiver.setEnabled(not c.actif)

    def __apres(self, r, message: str) -> None:
        self.bandeau.afficher(r, message)
        if self.__comptes.profil().ok:
            self.actualiser()
        else:
            self.accept()  # l'administrateur s'est desactive lui-meme : retour a la connexion

    def __role(self, attribuer: bool) -> None:
        c = self.__choisi()
        if c is None:
            return
        if attribuer:
            roles = [r for r in ROLES if r not in c.roles]
            d = DialogueRole("Attribuer un rôle", c.nom, roles, "&Attribuer", self)
        else:
            d = DialogueRole("Retirer un rôle", c.nom, list(c.roles), "&Retirer", self)
        if not d.liste.count():
            self.bandeau.refus(f"{c.nom} a déjà tous les rôles")
            return
        if d.exec():
            if attribuer:
                self.__apres(self.__comptes.attribuer_role(c.numero, d.role), f"rôle {d.liste.currentText()} attribué à {c.nom}")
            else:
                self.__apres(self.__comptes.retirer_role(c.numero, d.role), f"rôle {d.liste.currentText()} retiré à {c.nom}")

    def __desactiver(self) -> None:
        c = self.__choisi()
        d = DialogueConfirmation("Désactiver un compte", f"Désactiver le compte de {c.nom} ? Il ne pourra plus se "
                                 "connecter, mais reste auteur et assigné de ses tickets.", "&Désactiver", self)
        if d.exec():
            self.__apres(self.__comptes.desactiver(c.numero), f"compte de {c.nom} désactivé")

    def __reactiver(self) -> None:
        c = self.__choisi()
        self.__apres(self.__comptes.reactiver(c.numero), f"compte de {c.nom} réactivé")
