"""F3 Fenetre principale : liste des tickets, filtres, archives, menus selon les roles."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
                               QTableView, QTabWidget, QVBoxLayout, QWidget)

from application import ASSIGNES_A_MOI, MES_TICKETS, TOUS, Permission, Priority, Status

from .. import libelles, theme
from ..widgets import BandeauResultat, DelegatePastille, bouton, etiquette

COLONNES = ["N°", "Titre", "Statut", "Priorité", "Auteur", "Assigné", "Modifié le"]


def _tableau(nom_accessible: str) -> (QTableView, QStandardItemModel):
    modele = QStandardItemModel(0, len(COLONNES))
    modele.setHorizontalHeaderLabels(COLONNES)
    vue = QTableView()
    vue.setModel(modele)
    vue.setAccessibleName(nom_accessible)
    vue.setSelectionBehavior(QAbstractItemView.SelectRows)
    vue.setSelectionMode(QAbstractItemView.SingleSelection)
    vue.setEditTriggers(QAbstractItemView.NoEditTriggers)
    vue.setTabKeyNavigation(False)  # Tab sort du tableau ; les fleches s'y deplacent (WCAG 2.1.2)
    vue.setAlternatingRowColors(True)
    vue.setWordWrap(False)
    vue.verticalHeader().hide()
    vue.setItemDelegateForColumn(2, DelegatePastille(vue))
    vue.setItemDelegateForColumn(3, DelegatePastille(vue))
    entete = vue.horizontalHeader()
    entete.setSectionResizeMode(QHeaderView.ResizeToContents)
    entete.setSectionResizeMode(1, QHeaderView.Stretch)
    entete.setHighlightSections(False)
    return vue, modele


def _remplir(modele: QStandardItemModel, lignes) -> None:
    modele.removeRows(0, modele.rowCount())
    for l in lignes:
        statut, priorite = theme.STATUTS[l.statut][0], theme.PRIORITES[l.priorite][0]
        valeurs = [str(l.numero), l.titre, statut, priorite, l.auteur, l.assigne or "aucun",
                   l.modifie_le.strftime("%Y-%m-%d %H:%M")]
        items = [QStandardItem(v) for v in valeurs]
        items[0].setData(l.numero, Qt.UserRole + 1)
        items[2].setData(l.statut, Qt.UserRole)
        items[3].setData(l.priorite, Qt.UserRole)
        items[2].setAccessibleText(f"Statut {statut}")
        items[3].setAccessibleText(f"Priorité {priorite}")
        modele.appendRow(items)


class FenetrePrincipale(QMainWindow):
    deconnexion = Signal()

    def __init__(self, comptes, tickets, taille_texte, aide=None, parent=None) -> None:
        super().__init__(parent)
        self.__comptes, self.__tickets, self.__taille = comptes, tickets, taille_texte
        self.__aide = aide
        self.__details = {}
        self.profil = comptes.profil().valeur
        self.setWindowTitle(f"Gestionnaire de tickets, {self.profil.nom}")
        self.resize(1000, 640)
        self.__menus()

        self.bandeau = BandeauResultat()
        self.filtre = QComboBox()
        self.filtre.addItem("Mes tickets (auteur ou assigné)", MES_TICKETS)
        self.filtre.addItem("Assignés à moi", ASSIGNES_A_MOI)
        if self.peut(Permission.VIEW_ALL):
            self.filtre.addItem("Tous les tickets", TOUS)
        self.statut = QComboBox()
        self.statut.addItem("Tous les statuts", None)
        for s in Status:
            self.statut.addItem(theme.STATUTS[s][0], s)
        self.priorite = QComboBox()
        self.priorite.addItem("Toutes les priorités", None)
        for p in Priority:
            self.priorite.addItem(theme.PRIORITES[p][0], p)
        if self.peut(Permission.VIEW_ALL):  # developpeurs et admins : tous les tickets par defaut
            self.filtre.setCurrentIndex(self.filtre.findData(TOUS))
        for combo in (self.filtre, self.statut, self.priorite):
            combo.currentIndexChanged.connect(self.actualiser)  # filtre la liste, sans changer de fenetre

        filtres = QHBoxLayout()
        for texte, combo in (("A&fficher :", self.filtre), ("&Statut :", self.statut),
                             ("&Priorité :", self.priorite)):
            libelle = QLabel(texte)
            libelle.setBuddy(combo)
            combo.setAccessibleName(texte.replace("&", "").rstrip(" :"))
            filtres.addWidget(libelle)
            filtres.addWidget(combo)
        filtres.addStretch(1)

        self.bouton_ouvrir = bouton("&Ouvrir le ticket", "Ouvrir le ticket sélectionné")
        self.bouton_ouvrir.clicked.connect(self.ouvrir_selection)
        actions = QHBoxLayout()
        if self.peut(Permission.CREATE):
            self.bouton_nouveau = bouton("&Nouveau ticket", role="principal")
            self.bouton_nouveau.clicked.connect(self.nouveau_ticket)
            actions.addWidget(self.bouton_nouveau)
        actions.addWidget(self.bouton_ouvrir)
        actions.addStretch(1)
        self.compte_lignes = etiquette("", "secondaire", enveloppe=False)
        actions.addWidget(self.compte_lignes)

        self.vue_actifs, self.modele_actifs = _tableau("Tickets actifs")
        self.vue_archives, self.modele_archives = _tableau("Tickets archivés")
        for vue in (self.vue_actifs, self.vue_archives):
            vue.activated.connect(self.ouvrir_index)
            vue.doubleClicked.connect(self.ouvrir_index)
        self.onglets = QTabWidget()
        self.onglets.setAccessibleName("Listes de tickets : actifs ou archivés")
        self.onglets.addTab(self.vue_actifs, "Tickets &actifs")
        self.onglets.addTab(self.vue_archives, "A&rchives")
        self.onglets.currentChanged.connect(lambda _: self.__compter())

        centre = QWidget()
        colonne = QVBoxLayout(centre)
        colonne.setContentsMargins(16, 12, 16, 12)
        colonne.setSpacing(10)
        colonne.addWidget(self.bandeau)
        colonne.addLayout(filtres)
        colonne.addLayout(actions)
        colonne.addWidget(self.onglets, 1)
        self.setCentralWidget(centre)
        roles = libelles.roles(self.profil.roles)
        self.statusBar().addWidget(etiquette(f"Connecté : {self.profil.nom} ({roles})", enveloppe=False))
        self.actualiser()
        self.vue_actifs.setFocus()

    # ------------------------------------------------ menus
    def peut(self, p) -> bool:
        return p in self.profil.permissions

    def __action(self, menu, texte, rappel, raccourci=None) -> QAction:
        action = QAction(texte, self)
        if raccourci:
            action.setShortcut(QKeySequence(raccourci))
        action.triggered.connect(rappel)
        menu.addAction(action)
        return action

    def __menus(self) -> None:
        barre = self.menuBar()
        m = barre.addMenu("&Ticket")
        if self.peut(Permission.CREATE):
            self.__action(m, "&Nouveau ticket…", self.nouveau_ticket, "Ctrl+N")
        self.__action(m, "&Ouvrir le ticket sélectionné", self.ouvrir_selection, "Ctrl+O")
        self.__action(m, "&Actualiser", self.actualiser, "F5")
        m.addSeparator()
        self.__action(m, "Se &déconnecter", self.se_deconnecter)
        self.__action(m, "&Quitter", self.close, "Ctrl+Q")

        m = barre.addMenu("&Comptes")
        self.__action(m, "Mon &profil", self.ouvrir_profil)
        if self.peut(Permission.MANAGE_USERS):
            self.__action(m, "&Gestion des comptes…", self.ouvrir_gestion_comptes)

        m = barre.addMenu("A&ffichage")
        groupe = QActionGroup(self)
        sous_menu = m.addMenu("&Taille du texte")
        self.actions_taille = {}
        for e in theme.ECHELLES:
            a = QAction(f"{e} %", self, checkable=True)
            a.setChecked(e == self.__taille.echelle)
            a.triggered.connect(lambda _=False, e=e: self.regler_taille(e))
            groupe.addAction(a)
            sous_menu.addAction(a)
            self.actions_taille[e] = a
        self.__action(m, "&Agrandir le texte", lambda: self.regler_taille(None, +1), "Ctrl++")
        self.__action(m, "&Réduire le texte", lambda: self.regler_taille(None, -1), "Ctrl+-")

        m = barre.addMenu("&Aide")
        self.__action(m, "&Aide et accessibilité", self.ouvrir_aide, "F1")

    def regler_taille(self, echelle=None, pas=0) -> None:
        if echelle is not None:
            self.__taille.regler(echelle)
        elif pas > 0:
            self.__taille.plus()
        else:
            self.__taille.moins()
        self.actions_taille[self.__taille.echelle].setChecked(True)
        for vue in (self.vue_actifs, self.vue_archives):
            vue.resizeRowsToContents()
        self.bandeau.information(f"Taille du texte : {self.__taille.echelle} %")

    # ------------------------------------------------ liste
    def actualiser(self) -> None:
        r = self.__tickets.lister(self.filtre.currentData(), self.statut.currentData(), self.priorite.currentData())
        if r.ok:
            _remplir(self.modele_actifs, r.valeur)
        else:
            self.bandeau.refus(r.motif)
        a = self.__tickets.archives()
        _remplir(self.modele_archives, a.valeur if a.ok else [])
        for vue in (self.vue_actifs, self.vue_archives):
            vue.resizeRowsToContents()
            if vue.model().rowCount() and not vue.currentIndex().isValid():
                vue.setCurrentIndex(vue.model().index(0, 0))
        self.__compter()

    def __compter(self) -> None:
        vue = self.onglets.currentWidget()
        n = vue.model().rowCount()
        self.compte_lignes.setText(f"{n} ticket{'s' if n > 1 else ''}")
        self.bouton_ouvrir.setEnabled(n > 0)

    def numero_selectionne(self):
        vue = self.onglets.currentWidget()
        index = vue.currentIndex()
        if not index.isValid():
            return None
        return vue.model().index(index.row(), 0).data(Qt.UserRole + 1)

    # ------------------------------------------------ ouvertures
    def ouvrir_index(self, index) -> None:
        self.ouvrir_ticket(index.model().index(index.row(), 0).data(Qt.UserRole + 1))

    def ouvrir_selection(self) -> None:
        numero = self.numero_selectionne()
        if numero is None:
            self.bandeau.refus("aucun ticket sélectionné")
            return
        self.ouvrir_ticket(numero)

    def ouvrir_ticket(self, numero: int) -> None:
        from .detail import FenetreDetail
        fenetre = self.__details.get(numero)
        if fenetre is None or not fenetre.isVisible():
            fenetre = FenetreDetail(self.__tickets, numero, self)
            fenetre.modifie.connect(self.actualiser)
            self.__details[numero] = fenetre
        if fenetre.charger():
            fenetre.show()
            fenetre.raise_()
            fenetre.activateWindow()
        else:
            self.bandeau.refus(fenetre.motif)

    def nouveau_ticket(self) -> None:
        from .nouveau import FenetreNouveauTicket
        dialogue = FenetreNouveauTicket(self.__tickets, self)
        if dialogue.exec():
            r = dialogue.resultat
            self.actualiser()
            self.bandeau.succes(f"ticket {r.valeur} créé", r.details)
            self.ouvrir_ticket(r.valeur)

    def ouvrir_profil(self) -> None:
        from .profil import FenetreProfil
        FenetreProfil(self.__comptes.profil().valeur, self).exec()

    def ouvrir_gestion_comptes(self) -> None:
        from .comptes import FenetreComptes
        FenetreComptes(self.__comptes, self).exec()
        if self.__comptes.profil().ok:
            self.actualiser()
        else:  # l'administrateur s'est desactive lui-meme
            self.se_deconnecter()

    def ouvrir_aide(self) -> None:
        from .aide import FenetreAide
        FenetreAide(self.__aide or (), self).exec()

    def se_deconnecter(self) -> None:
        for fenetre in self.__details.values():
            fenetre.close()
        self.__comptes.deconnecter()
        self.deconnexion.emit()
        self.close()
