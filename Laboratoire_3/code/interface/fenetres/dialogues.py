"""F7 Dialogues d'action : motif, assignation, priorite, titre, confirmation."""
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLineEdit, QPlainTextEdit, QVBoxLayout)

from application import Priority

from .. import theme
from ..widgets import BandeauResultat, Champ, bouton, etiquette


class _Dialogue(QDialog):
    """Squelette commun : consigne, champ, bandeau, boutons OK et Annuler (Echap annule)."""

    def __init__(self, titre: str, consigne: str, texte_ok: str, parent=None, role_ok="principal") -> None:
        super().__init__(parent)
        self.setWindowTitle(titre)
        self.setMinimumWidth(460)
        self.bandeau = BandeauResultat()
        self.colonne = QVBoxLayout(self)
        self.colonne.setContentsMargins(20, 16, 20, 16)
        self.colonne.setSpacing(12)
        if consigne:
            self.colonne.addWidget(etiquette(consigne, "secondaire"))
        self.colonne.addWidget(self.bandeau)
        self.ok = bouton(texte_ok, role=role_ok)
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.valider)
        self.annuler = bouton("Annuler")
        self.annuler.clicked.connect(self.reject)
        self.__boutons = QHBoxLayout()
        self.__boutons.addWidget(self.ok)
        self.__boutons.addStretch(1)
        self.__boutons.addWidget(self.annuler)

    def terminer(self, *champs) -> None:
        for c in champs:
            self.colonne.addWidget(c)
        self.colonne.addLayout(self.__boutons)

    def valider(self) -> None:
        self.accept()


class DialogueMotif(_Dialogue):
    """Rejeter, fermer ou rouvrir : le motif est obligatoire et devient un commentaire."""

    def __init__(self, titre: str, action: str, parent=None) -> None:
        super().__init__(titre, "Le motif est obligatoire. Il sera ajouté aux commentaires du ticket.",
                         action, parent)
        self.texte = QPlainTextEdit()
        self.texte.setTabChangesFocus(True)  # Tab sort de la zone de texte (WCAG 2.1.2)
        self.texte.setMinimumHeight(90)
        self.champ = Champ("&Motif", self.texte, obligatoire=True)
        self.terminer(self.champ)
        self.texte.setFocus()

    @property
    def motif(self) -> str:
        return self.texte.toPlainText()

    def valider(self) -> None:
        if not self.motif.strip():
            self.champ.erreur("écrivez le motif")
            self.texte.setFocus()
            return
        self.accept()


class DialogueAssigner(_Dialogue):

    def __init__(self, comptes, assigne_actuel, parent=None) -> None:
        super().__init__("Assigner le ticket", "Seuls les comptes actifs ayant le rôle Développeur sont proposés.",
                         "A&ssigner", parent)
        self.liste = QComboBox()
        for c in comptes:
            self.liste.addItem(c.nom + (" (assigné actuel)" if c.nom == assigne_actuel else ""), c.numero)
        self.terminer(Champ("&Développeur", self.liste))
        self.liste.setFocus()

    @property
    def numero(self) -> int:
        return self.liste.currentData()


class DialoguePriorite(_Dialogue):

    def __init__(self, actuelle, parent=None) -> None:
        super().__init__("Changer la priorité", f"Priorité actuelle : {theme.PRIORITES[actuelle][0]}.",
                         "&Changer", parent)
        self.liste = QComboBox()
        for p in Priority:
            self.liste.addItem(theme.PRIORITES[p][0], p)
        self.liste.setCurrentIndex(list(Priority).index(actuelle))
        self.terminer(Champ("&Nouvelle priorité", self.liste))
        self.liste.setFocus()

    @property
    def priorite(self):
        return self.liste.currentData()


class DialogueTitre(_Dialogue):

    def __init__(self, actuel: str, parent=None) -> None:
        super().__init__("Modifier le titre", "200 caractères au plus, sur une seule ligne.", "&Enregistrer", parent)
        self.texte = QLineEdit(actuel)
        self.texte.setMaxLength(200)
        self.champ = Champ("&Titre", self.texte, obligatoire=True)
        self.terminer(self.champ)
        self.texte.selectAll()
        self.texte.setFocus()

    @property
    def titre(self) -> str:
        return self.texte.text()

    def valider(self) -> None:
        if not self.titre.strip():
            self.champ.erreur("le titre est vide")
            return
        self.accept()


class DialogueConfirmation(_Dialogue):
    """Action definitive : on demande confirmation (WCAG 3.3.4). Annuler a le focus par defaut."""

    def __init__(self, titre: str, message: str, texte_ok: str, parent=None) -> None:
        super().__init__(titre, "", texte_ok, parent, role_ok="danger")
        self.colonne.insertWidget(0, etiquette(message))
        self.terminer()
        self.ok.setDefault(False)
        self.annuler.setDefault(True)
        self.annuler.setFocus()
