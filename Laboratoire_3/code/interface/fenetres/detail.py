"""F4 Detail du ticket : en-tete, description (texte et images), commentaires, actions."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea,
                               QVBoxLayout, QWidget)

from application import BlocCommentaire, BlocImage, BlocTexte, BlocTicket, BlocVideo, Permission

from .. import theme
from ..libelles import ACTIONS_TICKET
from ..widgets import BandeauResultat, Pastille, bouton, etiquette

LARGEUR_IMAGE_MAX = 640


def _date(d) -> str:
    return d.strftime("%Y-%m-%d %H:%M") if d else ""


def _zone() -> QFrame:
    cadre = QFrame()
    cadre.setProperty("role", "zone")
    return cadre


def _titre_section(texte: str) -> QLabel:
    label = etiquette(texte, "titre")
    police = label.font()
    police.setPointSizeF(police.pointSizeF() * 1.15)
    label.setFont(police)
    label.setAccessibleName(texte)
    return label


def vue_image(bloc: BlocImage) -> QWidget:
    """Image reduite a 640 px de large au plus, avec son texte de remplacement visible et lu."""
    cadre = _zone()
    colonne = QVBoxLayout(cadre)
    image = QLabel()
    image.setAccessibleName(bloc.texte_de_remplacement)
    lecteur = QImageReader(bloc.chemin)
    taille = lecteur.size()
    if bloc.lisible and taille.isValid():
        if taille.width() > LARGEUR_IMAGE_MAX:
            taille = QSize(LARGEUR_IMAGE_MAX, int(taille.height() * LARGEUR_IMAGE_MAX / taille.width()))
            lecteur.setScaledSize(taille)
        img = lecteur.read()
        if not img.isNull():
            image.setPixmap(QPixmap.fromImage(img))
    if image.pixmap().isNull():
        image.setText("(image illisible)")
    colonne.addWidget(image, 0, Qt.AlignLeft)
    colonne.addWidget(etiquette(bloc.texte_de_remplacement, "secondaire"))
    return cadre


class FenetreDetail(QDialog):
    """Fenetre non modale : plusieurs tickets peuvent etre ouverts en meme temps."""
    modifie = Signal()

    def __init__(self, tickets, numero: int, principale) -> None:
        super().__init__(principale)
        self.setModal(False)
        self.__tickets, self.numero, self.__principale = tickets, numero, principale
        self.motif = None
        self.detail = None
        self.resize(820, 720)

        self.bandeau = BandeauResultat()
        self.titre = etiquette("", "titre")
        police = self.titre.font()
        police.setPointSizeF(police.pointSizeF() * 1.4)
        self.titre.setFont(police)
        self.titre.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.pastille_statut = None
        self.pastille_priorite = None
        self.ligne_pastilles = QHBoxLayout()
        self.infos = etiquette("", "secondaire")

        # description et commentaires dans une zone qui defile (WCAG 1.4.10)
        self.contenu = QWidget()
        self.colonne_contenu = QVBoxLayout(self.contenu)
        self.colonne_contenu.setContentsMargins(0, 0, 8, 0)
        self.colonne_contenu.setSpacing(10)
        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setWidget(self.contenu)
        defilement.setFocusPolicy(Qt.StrongFocus)
        defilement.setAccessibleName("Description et commentaires")

        # commenter
        self.nouveau_commentaire = QPlainTextEdit()
        self.nouveau_commentaire.setTabChangesFocus(True)
        self.nouveau_commentaire.setPlaceholderText("Votre commentaire")
        self.nouveau_commentaire.setMaximumHeight(90)
        self.nouveau_commentaire.setAccessibleName("Nouveau commentaire")
        libelle_commentaire = QLabel("No&uveau commentaire")
        libelle_commentaire.setBuddy(self.nouveau_commentaire)
        libelle_commentaire.setProperty("role", "titre")
        self.bouton_commenter = bouton("&Publier le commentaire")
        self.bouton_commenter.clicked.connect(self.commenter)

        # actions : visibles selon les roles, actives selon allowed_actions
        self.boutons = {}
        grille = QGridLayout()
        grille.setSpacing(8)
        visibles = [a for a in ACTIONS_TICKET if a[0] in principale.profil.permissions]
        for i, (permission, texte, _) in enumerate(visibles):
            b = bouton(texte, role="danger" if permission is Permission.ARCHIVE else None)
            b.clicked.connect(lambda _=False, p=permission: self.agir(p))
            self.boutons[permission] = b
            grille.addWidget(b, i // 2, i % 2)
        self.possibles = etiquette("", "secondaire")
        self.bouton_fermer_fenetre = bouton("Fermer la fe&nêtre")
        self.bouton_fermer_fenetre.clicked.connect(self.close)

        actions = QVBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(_titre_section("Actions"))
        actions.addLayout(grille)
        actions.addWidget(self.possibles)
        actions.addStretch(1)
        actions.addWidget(libelle_commentaire)
        actions.addWidget(self.nouveau_commentaire)
        actions.addWidget(self.bouton_commenter)
        actions.addWidget(self.bouton_fermer_fenetre)
        panneau_actions = QWidget()
        panneau_actions.setLayout(actions)
        # le panneau garde la largeur de ses boutons ; s'il manque de hauteur (texte a 200 %), il defile
        defilement_actions = QScrollArea()
        defilement_actions.setAccessibleName("Actions et commentaire")
        defilement_actions.setWidgetResizable(True)
        defilement_actions.setWidget(panneau_actions)
        defilement_actions.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        defilement_actions.setMinimumWidth(panneau_actions.sizeHint().width() + 24)
        self.__panneau_actions, self.__defilement_actions = panneau_actions, defilement_actions

        corps = QHBoxLayout()
        corps.addWidget(defilement, 1)
        corps.addWidget(defilement_actions, 0)

        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(16, 12, 16, 12)
        colonne.setSpacing(10)
        colonne.addWidget(self.bandeau)
        colonne.addWidget(self.titre)
        colonne.addLayout(self.ligne_pastilles)
        colonne.addWidget(self.infos)
        colonne.addLayout(corps, 1)

    # ------------------------------------------------ chargement
    def charger(self) -> bool:
        r = self.__tickets.detail(self.numero)
        if not r.ok:
            self.motif = r.motif
            return False
        self.detail = r.valeur
        self.__afficher()
        return True

    def __vider(self) -> None:
        while self.colonne_contenu.count():
            element = self.colonne_contenu.takeAt(0)
            if element.widget():
                element.widget().hide()
                element.widget().deleteLater()

    def __afficher(self) -> None:
        d = self.detail
        tete = d.blocs[0]
        assert isinstance(tete, BlocTicket)
        self.setWindowTitle(f"Ticket {tete.numero} : {tete.titre}")
        self.titre.setText(f"Ticket {tete.numero} : {tete.titre}")
        while self.ligne_pastilles.count():  # retirer tout de suite l'ancienne ligne (pastilles, mention d'archive)
            ancien = self.ligne_pastilles.takeAt(0).widget()
            if ancien is not None:
                ancien.hide()
                ancien.deleteLater()
        statut = next(s for s in theme.STATUTS if s.value == tete.statut)
        priorite = next(p for p in theme.PRIORITES if p.value == tete.priorite)
        self.pastille_statut, self.pastille_priorite = Pastille(statut), Pastille(priorite)
        self.ligne_pastilles.addWidget(self.pastille_statut)
        self.ligne_pastilles.addWidget(self.pastille_priorite)
        if tete.archive_le:
            self.ligne_pastilles.addWidget(etiquette(f"Archivé le {_date(tete.archive_le)} : lecture seule",
                                                     "secondaire", enveloppe=False))
        self.ligne_pastilles.addStretch(1)
        self.infos.setText(f"Auteur : {tete.auteur}    Assigné : {tete.assigne or 'aucun'}    "
                           f"Créé le {_date(tete.cree_le)}    Modifié le {_date(tete.modifie_le)}")

        self.__vider()
        textes = [b for b in d.blocs if isinstance(b, (BlocTexte, BlocImage, BlocVideo))]
        commentaires = [b for b in d.blocs if isinstance(b, BlocCommentaire)]
        self.colonne_contenu.addWidget(_titre_section("Description"))
        if not textes:
            self.colonne_contenu.addWidget(etiquette("Aucune description pour l'instant.", "secondaire"))
        for b in textes:
            if isinstance(b, BlocTexte):
                cadre = _zone()
                c = QVBoxLayout(cadre)
                c.addWidget(etiquette(f"Texte : {b.nom}", "secondaire"))
                texte = etiquette(b.texte.rstrip("\n"))
                texte.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
                c.addWidget(texte)
                self.colonne_contenu.addWidget(cadre)
            elif isinstance(b, BlocImage):
                self.colonne_contenu.addWidget(vue_image(b))
            else:
                self.colonne_contenu.addWidget(
                    etiquette(f"Vidéo jointe ({b.nom}) : non prise en charge dans cette version.", "secondaire"))
        self.colonne_contenu.addWidget(_titre_section(f"Commentaires ({len(commentaires)})"))
        if not commentaires:
            self.colonne_contenu.addWidget(etiquette("Aucun commentaire.", "secondaire"))
        for b in commentaires:
            cadre = _zone()
            c = QVBoxLayout(cadre)
            c.addWidget(etiquette(f"{b.auteur}, le {_date(b.publie_le)}", "secondaire"))
            c.addWidget(etiquette(b.texte))
            self.colonne_contenu.addWidget(cadre)
        self.colonne_contenu.addStretch(1)

        permises = d.actions
        noms = [nom for p, _, nom in ACTIONS_TICKET if p in permises and p in self.boutons]
        for p, b in self.boutons.items():
            b.setEnabled(p in permises)
        self.bouton_commenter.setEnabled(Permission.COMMENT in permises)
        self.nouveau_commentaire.setEnabled(Permission.COMMENT in permises)
        self.__defilement_actions.setMinimumWidth(self.__panneau_actions.sizeHint().width() + 24)
        statut_libelle = theme.STATUTS[statut][0]
        self.possibles.setText(f"Possible maintenant, en {statut_libelle} : " + (", ".join(noms) if noms else
                               "aucune action de la liste."))

    # ------------------------------------------------ actions
    def __apres(self, resultat, message: str) -> None:
        self.bandeau.afficher(resultat, message)
        if resultat.ok:
            self.charger()
            self.modifie.emit()

    def commenter(self) -> None:
        texte = self.nouveau_commentaire.toPlainText()
        if not texte.strip():
            self.bandeau.refus("le commentaire est vide")
            self.nouveau_commentaire.setFocus()
            return
        r = self.__tickets.commenter(self.numero, texte)
        if r.ok:
            self.nouveau_commentaire.clear()
        self.__apres(r, "commentaire publié")

    def agir(self, p) -> None:
        from .ajout import DialogueAjout
        from .dialogues import DialogueAssigner, DialogueConfirmation, DialogueMotif, DialoguePriorite, DialogueTitre
        t, n = self.__tickets, self.numero
        tete = self.detail.blocs[0]
        if p is Permission.EDIT:
            d = DialogueTitre(tete.titre, self)
            if d.exec():
                self.__apres(t.modifier_titre(n, d.titre), "titre modifié")
        elif p is Permission.ATTACH:
            d = DialogueAjout(t, n, self)
            if d.exec():
                self.__apres(d.resultat, d.message)
        elif p is Permission.ASSIGN:
            comptes = t.assignables()
            d = DialogueAssigner(comptes.valeur if comptes.ok else [], tete.assigne, self)
            if d.exec():
                self.__apres(t.assigner(n, d.numero), f"ticket assigné à {d.liste.currentText()}")
        elif p is Permission.SUBMIT:
            self.__apres(t.soumettre(n), "travail soumis à la validation")
        elif p is Permission.VALIDATE:
            self.__apres(t.valider(n), "travail validé : le ticket est TERMINÉ")
        elif p in (Permission.REJECT, Permission.CLOSE, Permission.REOPEN):
            titres = {Permission.REJECT: ("Rejeter le travail", "&Rejeter", t.rejeter, "travail rejeté"),
                      Permission.CLOSE: ("Fermer le ticket", "&Fermer le ticket", t.fermer, "ticket fermé"),
                      Permission.REOPEN: ("Rouvrir le ticket", "R&ouvrir", t.rouvrir, "ticket rouvert")}
            titre, action, appel, message = titres[p]
            d = DialogueMotif(titre, action, self)
            if d.exec():
                self.__apres(appel(n, d.motif), message)
        elif p is Permission.SET_PRIORITY:
            priorite = next(pr for pr in theme.PRIORITES if pr.value == tete.priorite)
            d = DialoguePriorite(priorite, self)
            if d.exec():
                self.__apres(t.changer_priorite(n, d.priorite), f"priorité : {d.liste.currentText()}")
        elif p is Permission.ARCHIVE:
            d = DialogueConfirmation("Archiver le ticket",
                                     f"Archiver le ticket {n} ? L'archivage est définitif : le ticket restera "
                                     "consultable, mais plus aucune modification ne sera possible.", "&Archiver", self)
            if d.exec():
                self.__apres(t.archiver(n), "ticket archivé")
