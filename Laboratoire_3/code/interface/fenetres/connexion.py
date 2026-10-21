"""F1 Connexion et F2 Creer un compte."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLineEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QAbstractItemView, QHeaderView)

from ..widgets import BandeauResultat, Champ, bouton, etiquette


def _champ_mot_de_passe() -> QLineEdit:
    """Masque a l'ecran, mais coller et gestionnaire de mots de passe permis (WCAG 3.3.8)."""
    champ = QLineEdit()
    champ.setEchoMode(QLineEdit.Password)
    champ.setInputMethodHints(Qt.ImhHiddenText | Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase)
    return champ


class FenetreConnexion(QDialog):
    """F1 : courriel et mot de passe. accept() quand le service a ouvert la session."""

    def __init__(self, comptes, comptes_demo=(), parent=None) -> None:
        super().__init__(parent)
        self.__comptes = comptes
        self.setWindowTitle("Connexion au gestionnaire de tickets")
        self.setMinimumWidth(420)

        titre = etiquette("Gestionnaire de tickets", "titre")
        police = titre.font()
        police.setPointSizeF(police.pointSizeF() * 1.4)
        titre.setFont(police)
        titre.setAccessibleName("Gestionnaire de tickets, connexion")
        intro = etiquette("Connectez-vous avec votre courriel et votre mot de passe.", "secondaire")

        self.bandeau = BandeauResultat()
        self.courriel = QLineEdit()
        self.courriel.setInputMethodHints(Qt.ImhEmailCharactersOnly | Qt.ImhNoAutoUppercase)
        self.champ_courriel = Champ("&Courriel", self.courriel, obligatoire=True)
        self.mot_de_passe = _champ_mot_de_passe()
        self.champ_mdp = Champ("&Mot de passe", self.mot_de_passe, obligatoire=True)
        self.afficher_mdp = QCheckBox("&Afficher le mot de passe")
        self.afficher_mdp.toggled.connect(
            lambda oui: self.mot_de_passe.setEchoMode(QLineEdit.Normal if oui else QLineEdit.Password))

        self.bouton_connecter = bouton("Se &connecter", role="principal")
        self.bouton_connecter.setDefault(True)
        self.bouton_connecter.clicked.connect(self.connecter)
        self.bouton_inscrire = bouton("Créer un c&ompte")
        self.bouton_inscrire.clicked.connect(self.inscrire)
        self.bouton_quitter = bouton("&Quitter")
        self.bouton_quitter.clicked.connect(self.reject)

        boutons = QHBoxLayout()
        boutons.addWidget(self.bouton_connecter)
        boutons.addWidget(self.bouton_inscrire)
        boutons.addStretch(1)
        boutons.addWidget(self.bouton_quitter)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(24, 20, 24, 20)
        colonne.setSpacing(12)
        for w in (titre, intro, self.bandeau, self.champ_courriel, self.champ_mdp, self.afficher_mdp):
            colonne.addWidget(w)
        colonne.addLayout(boutons)

        self.tableau_demo = None
        if comptes_demo:
            self.bouton_demo = QPushButton("Afficher les comptes de &démonstration")
            self.bouton_demo.setCheckable(True)
            self.bouton_demo.setMinimumHeight(32)
            self.tableau_demo = self.__tableau_demo(comptes_demo)
            self.tableau_demo.hide()
            self.bouton_demo.toggled.connect(self.__basculer_demo)
            colonne.addWidget(self.bouton_demo)
            colonne.addWidget(self.tableau_demo)

        ordre = [self.courriel, self.mot_de_passe, self.afficher_mdp, self.bouton_connecter,
                 self.bouton_inscrire, self.bouton_quitter]
        if self.tableau_demo is not None:
            ordre += [self.bouton_demo, self.tableau_demo]
        for a, b in zip(ordre, ordre[1:]):
            self.setTabOrder(a, b)
        self.courriel.setFocus()

    def __tableau_demo(self, comptes_demo) -> QTableWidget:
        t = QTableWidget(len(comptes_demo), 3)
        t.setAccessibleName("Comptes de démonstration")
        t.setHorizontalHeaderLabels(["Courriel", "Mot de passe", "Rôles"])
        t.verticalHeader().hide()
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        for i, (_, courriel, mdp, roles) in enumerate(comptes_demo):
            for j, valeur in enumerate((courriel, mdp, roles)):
                t.setItem(i, j, QTableWidgetItem(valeur))
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        t.setMinimumHeight(t.verticalHeader().length() + t.horizontalHeader().height() + 6)
        t.cellActivated.connect(lambda ligne, _: self.__remplir(t, ligne))
        t.cellDoubleClicked.connect(lambda ligne, _: self.__remplir(t, ligne))
        t.setToolTip("Entrée ou double-clic : remplit le courriel et le mot de passe")
        return t

    def __remplir(self, t: QTableWidget, ligne: int) -> None:
        self.courriel.setText(t.item(ligne, 0).text())
        self.mot_de_passe.setText(t.item(ligne, 1).text())
        self.bouton_connecter.setFocus()

    def __basculer_demo(self, visible: bool) -> None:
        self.tableau_demo.setVisible(visible)
        self.bouton_demo.setText(("Masquer" if visible else "Afficher") + " les comptes de &démonstration")
        self.adjustSize()

    def connecter(self) -> None:
        self.champ_courriel.effacer_erreur()
        self.champ_mdp.effacer_erreur()
        manquants = []
        if not self.courriel.text().strip():
            self.champ_courriel.erreur("entrez votre courriel")
            manquants.append(self.courriel)
        if not self.mot_de_passe.text():
            self.champ_mdp.erreur("entrez votre mot de passe")
            manquants.append(self.mot_de_passe)
        if manquants:
            self.bandeau.refus("des champs obligatoires sont vides")
            manquants[0].setFocus()
            return
        r = self.__comptes.connecter(self.courriel.text(), self.mot_de_passe.text())
        if not r.ok:
            self.bandeau.refus(r.motif)
            self.mot_de_passe.clear()
            self.mot_de_passe.setFocus()
            return
        self.accept()

    def inscrire(self) -> None:
        dialogue = FenetreInscription(self.__comptes, self)
        if dialogue.exec() == QDialog.Accepted:
            self.courriel.setText(dialogue.courriel.text().strip())
            self.mot_de_passe.clear()
            self.bandeau.succes(f"compte créé pour {dialogue.nom_cree}. Connectez-vous avec votre mot de passe.")
            self.mot_de_passe.setFocus()


class FenetreInscription(QDialog):
    """F2 : inscription libre ; le compte recoit le role Rapporteur."""

    def __init__(self, comptes, parent=None) -> None:
        super().__init__(parent)
        self.__comptes = comptes
        self.nom_cree = None
        self.setWindowTitle("Créer un compte")
        self.setMinimumWidth(440)
        intro = etiquette("Le nouveau compte reçoit le rôle Rapporteur : il peut créer des tickets, "
                          "les décrire et les commenter.", "secondaire")
        self.bandeau = BandeauResultat()
        self.nom = QLineEdit()
        self.courriel = QLineEdit()
        self.mot_de_passe = _champ_mot_de_passe()
        self.confirmation = _champ_mot_de_passe()
        self.champs = [
            Champ("&Nom", self.nom, obligatoire=True),
            Champ("&Courriel", self.courriel, "Exemple : prenom@uqac.ca", obligatoire=True),
            Champ("&Mot de passe", self.mot_de_passe,
                  "8 caractères au minimum. Une phrase de passe avec des espaces est acceptée.", obligatoire=True),
            Champ("Con&firmation du mot de passe", self.confirmation, obligatoire=True),
        ]
        self.creer = bouton("C&réer le compte", role="principal")
        self.creer.setDefault(True)
        self.creer.clicked.connect(self.valider)
        annuler = bouton("Annuler")
        annuler.clicked.connect(self.reject)
        boutons = QHBoxLayout()
        boutons.addWidget(self.creer)
        boutons.addStretch(1)
        boutons.addWidget(annuler)
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(24, 20, 24, 20)
        colonne.setSpacing(12)
        colonne.addWidget(intro)
        colonne.addWidget(self.bandeau)
        for c in self.champs:
            colonne.addWidget(c)
        colonne.addLayout(boutons)
        self.nom.setFocus()

    def valider(self) -> None:
        for c in self.champs:
            c.effacer_erreur()
        vides = [c for c in self.champs if not c.widget.text().strip()]
        for c in vides:
            c.erreur("ce champ est obligatoire")
        if vides:
            self.bandeau.refus("des champs obligatoires sont vides")
            vides[0].widget.setFocus()
            return
        r = self.__comptes.inscrire(self.nom.text(), self.courriel.text(), self.mot_de_passe.text(),
                                    self.confirmation.text())
        if not r.ok:
            self.bandeau.refus(r.motif)
            cible = self.champs[3] if "identiques" in r.motif else None
            if cible:
                cible.erreur(r.motif)
                cible.widget.setFocus()
            return
        self.nom_cree = r.valeur
        self.accept()
