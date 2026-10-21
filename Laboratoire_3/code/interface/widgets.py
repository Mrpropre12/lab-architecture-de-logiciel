"""Widgets communs : chaque regle d'accessibilite y est ecrite une seule fois.

- Pastille : statut ou priorite, toujours libelle + icone + couleur (WCAG 1.4.1).
- DelegatePastille : la meme pastille dans un tableau ; le texte reste lu par le lecteur d'ecran.
- BandeauResultat : OK ou REFUSE avec le motif, annonce sans deplacer le focus (WCAG 4.1.3).
- Champ : etiquette liee (setBuddy), aide, message d'erreur sous le champ (WCAG 1.3.1, 3.3.1).
"""
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (QAccessible, QAccessibleAnnouncementEvent, QColor, QFontMetrics, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStyle,
                               QStyledItemDelegate, QVBoxLayout, QWidget)

from application import Priority, Status

from . import theme

# ---------------------------------------------------------------- annonces et texte brut


def annoncer(widget: QWidget, texte: str, assertif: bool = False) -> None:
    """Fait lire un message par le lecteur d'ecran sans deplacer le focus (WCAG 4.1.3)."""
    evenement = QAccessibleAnnouncementEvent(widget, texte)
    evenement.setPoliteness(QAccessible.AnnouncementPoliteness.Assertive if assertif
                            else QAccessible.AnnouncementPoliteness.Polite)
    QAccessible.updateAccessibility(evenement)


def etiquette(texte: str, role: str = None, enveloppe: bool = True) -> QLabel:
    """QLabel en texte brut : un texte saisi par un utilisateur n'est jamais interprete en HTML."""
    label = QLabel(texte)
    label.setTextFormat(Qt.PlainText)
    label.setWordWrap(enveloppe)
    if role:
        label.setProperty("role", role)
    return label


def bouton(texte: str, nom_accessible: str = None, role: str = None) -> QPushButton:
    b = QPushButton(texte)
    b.setMinimumHeight(theme.CIBLE_MIN)
    if nom_accessible:
        b.setAccessibleName(nom_accessible)
    if role:
        b.setProperty("role", role)
    return b


# ---------------------------------------------------------------- icones dessinees


def dessiner_icone(p: QPainter, r: QRectF, icone: str, couleur: QColor) -> None:
    """Icones simples et distinctes par leur forme (pas seulement par leur couleur)."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    stylo = QPen(couleur, max(1.5, r.width() / 8))
    stylo.setCapStyle(Qt.RoundCap)
    stylo.setJoinStyle(Qt.RoundJoin)
    p.setPen(stylo)
    p.setBrush(Qt.NoBrush)
    c = r.center()
    d = r.width() * 0.42
    if icone == "cercle":                       # OUVERT
        p.drawEllipse(c, d, d)
    elif icone == "personne":                   # ASSIGNE
        p.setBrush(couleur)
        p.drawEllipse(QPointF(c.x(), c.y() - d * 0.45), d * 0.38, d * 0.38)
        chemin = QPainterPath()
        chemin.moveTo(c.x() - d * 0.8, c.y() + d)
        chemin.quadTo(c.x(), c.y() - d * 0.2, c.x() + d * 0.8, c.y() + d)
        chemin.closeSubpath()
        p.drawPath(chemin)
    elif icone == "sablier":                    # VALIDATION
        chemin = QPainterPath()
        chemin.moveTo(c.x() - d * 0.7, c.y() - d)
        chemin.lineTo(c.x() + d * 0.7, c.y() - d)
        chemin.lineTo(c.x() - d * 0.7, c.y() + d)
        chemin.lineTo(c.x() + d * 0.7, c.y() + d)
        chemin.closeSubpath()
        p.drawPath(chemin)
    elif icone == "coche":                      # TERMINE
        chemin = QPainterPath()
        chemin.moveTo(c.x() - d * 0.85, c.y())
        chemin.lineTo(c.x() - d * 0.25, c.y() + d * 0.6)
        chemin.lineTo(c.x() + d * 0.9, c.y() - d * 0.7)
        p.drawPath(chemin)
    elif icone == "barre":                      # FERME : cercle barre
        p.drawEllipse(c, d, d)
        p.drawLine(QPointF(c.x() - d * 0.7, c.y() + d * 0.7), QPointF(c.x() + d * 0.7, c.y() - d * 0.7))
    elif icone in ("1", "2", "3"):              # priorites : 1, 2 ou 3 barres pleines sur 3
        p.setPen(Qt.NoPen)
        largeur = r.width() / 4.6
        for i in range(3):
            hauteur = r.height() * (0.35 + 0.3 * i)
            x = r.left() + i * (largeur * 1.6)
            barre = QRectF(x, r.bottom() - hauteur, largeur, hauteur)
            if i < int(icone):
                p.setBrush(couleur)
                p.drawRect(barre)
            else:
                p.setPen(QPen(couleur, 1))
                p.setBrush(Qt.NoBrush)
                p.drawRect(barre.adjusted(0.5, 0.5, -0.5, -0.5))
                p.setPen(Qt.NoPen)
    elif icone == "ok":                         # bandeau OK : coche dans un disque
        p.setBrush(couleur)
        p.setPen(Qt.NoPen)
        p.drawEllipse(c, d * 1.15, d * 1.15)
        stylo.setColor(QColor(theme.FOND))
        p.setPen(stylo)
        chemin = QPainterPath()
        chemin.moveTo(c.x() - d * 0.55, c.y())
        chemin.lineTo(c.x() - d * 0.12, c.y() + d * 0.45)
        chemin.lineTo(c.x() + d * 0.6, c.y() - d * 0.45)
        p.drawPath(chemin)
    elif icone == "refus":                      # bandeau REFUSE : croix dans un disque
        p.setBrush(couleur)
        p.setPen(Qt.NoPen)
        p.drawEllipse(c, d * 1.15, d * 1.15)
        stylo.setColor(QColor(theme.FOND))
        p.setPen(stylo)
        e = d * 0.5
        p.drawLine(QPointF(c.x() - e, c.y() - e), QPointF(c.x() + e, c.y() + e))
        p.drawLine(QPointF(c.x() - e, c.y() + e), QPointF(c.x() + e, c.y() - e))
    elif icone == "info":                       # bandeau d'information : i dans un disque
        p.setBrush(couleur)
        p.setPen(Qt.NoPen)
        p.drawEllipse(c, d * 1.15, d * 1.15)
        p.setBrush(QColor(theme.FOND))
        p.drawEllipse(QPointF(c.x(), c.y() - d * 0.55), d * 0.16, d * 0.16)
        p.drawRect(QRectF(c.x() - d * 0.13, c.y() - d * 0.2, d * 0.26, d * 0.85))
    p.restore()


def peindre_pastille(p: QPainter, r: QRect, libelle: str, fond: str, texte: str, icone: str, police) -> None:
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(fond))
    p.drawRoundedRect(QRectF(r), 6, 6)
    m = QFontMetrics(police)
    cote = m.height() * 0.85
    icone_r = QRectF(r.left() + 8, r.center().y() - cote / 2 + 0.5, cote, cote)
    dessiner_icone(p, icone_r, icone, QColor(texte))
    p.setPen(QColor(texte))
    gras = type(police)(police)
    gras.setBold(True)
    p.setFont(gras)
    zone = QRectF(icone_r.right() + 6, r.top(), r.right() - icone_r.right() - 12, r.height())
    p.drawText(zone, Qt.AlignVCenter | Qt.AlignLeft, libelle)
    p.restore()


def taille_pastille(libelle: str, police) -> QSize:
    gras = type(police)(police)
    gras.setBold(True)
    m = QFontMetrics(gras)
    return QSize(int(m.horizontalAdvance(libelle) + m.height() * 0.85 + 26), int(max(m.height() + 10, 26)))


def description_statut(s: Status):
    return theme.STATUTS[s]


def description_priorite(p: Priority):
    return theme.PRIORITES[p]


class Pastille(QWidget):
    """Statut ou priorite : couleur + icone + libelle. Le lecteur d'ecran lit « Statut : ASSIGNE »."""

    def __init__(self, valeur, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.changer(valeur)

    def changer(self, valeur) -> None:
        if isinstance(valeur, Status):
            self.__libelle, self.__fond, self.__texte, self.__icone = description_statut(valeur)
            prefixe = "Statut"
        else:
            self.__libelle, self.__fond, self.__texte, self.__icone = description_priorite(valeur)
            prefixe = "Priorité"
        self.setAccessibleName(f"{prefixe} : {self.__libelle}")
        self.setToolTip(f"{prefixe} : {self.__libelle}")
        self.updateGeometry()
        self.update()

    @property
    def libelle(self) -> str:
        return self.__libelle

    def sizeHint(self) -> QSize:
        return taille_pastille(self.__libelle, self.font())

    def paintEvent(self, _evenement) -> None:
        p = QPainter(self)
        peindre_pastille(p, self.rect(), self.__libelle, self.__fond, self.__texte, self.__icone, self.font())


class DelegatePastille(QStyledItemDelegate):
    """Dessine la pastille dans une cellule ; la valeur (Status ou Priority) est dans Qt.UserRole.
    Le texte de la cellule (DisplayRole) reste celui lu par le lecteur d'ecran."""

    def paint(self, p: QPainter, option, index) -> None:
        valeur = index.data(Qt.UserRole)
        if valeur is None:
            return super().paint(p, option, index)
        if option.state & QStyle.State_Selected:
            p.fillRect(option.rect, option.palette.highlight())
        libelle, fond, texte, icone = (description_statut(valeur) if isinstance(valeur, Status)
                                       else description_priorite(valeur))
        taille = taille_pastille(libelle, option.font)
        r = QRect(option.rect.left() + 6, option.rect.center().y() - taille.height() // 2 + 1,
                  min(taille.width(), option.rect.width() - 12), taille.height())
        if option.state & QStyle.State_Selected:  # contour pour rester distincte sur la selection
            p.save()
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(theme.FOND), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(r).adjusted(-2, -2, 2, 2), 7, 7)
            p.restore()
        peindre_pastille(p, r, libelle, fond, texte, icone, option.font)

    def sizeHint(self, option, index) -> QSize:
        valeur = index.data(Qt.UserRole)
        if valeur is None:
            return super().sizeHint(option, index)
        libelle = (description_statut(valeur) if isinstance(valeur, Status) else description_priorite(valeur))[0]
        t = taille_pastille(libelle, option.font)
        return QSize(t.width() + 12, t.height() + 10)


class _Icone(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.icone, self.couleur = "info", QColor(theme.INFORMATION)
        self.setFixedSize(26, 26)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, _evenement) -> None:
        dessiner_icone(QPainter(self), QRectF(self.rect()).adjusted(3, 3, -3, -3), self.icone, self.couleur)


class BandeauResultat(QFrame):
    """Resultat de la derniere action : icone, OK ou REFUSE, motif du modele, details.
    Il est annonce au lecteur d'ecran sans prendre le focus (WCAG 4.1.3)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("bandeau")
        self.setAccessibleName("Résultat de la dernière action")
        self.__icone = _Icone(self)
        self.__texte = etiquette("")
        self.__texte.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.__fermer = bouton("Fermer", "Fermer le message")
        self.__fermer.clicked.connect(self.hide)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(12, 8, 8, 8)
        ligne.addWidget(self.__icone, 0, Qt.AlignTop)
        ligne.addWidget(self.__texte, 1)
        ligne.addWidget(self.__fermer, 0, Qt.AlignTop)
        self.hide()

    @property
    def texte(self) -> str:
        return self.__texte.text()

    def __montrer(self, texte: str, icone: str, couleur: str, fond: str, assertif: bool) -> None:
        self.__icone.icone, self.__icone.couleur = icone, QColor(couleur)
        self.setStyleSheet(f"QFrame#bandeau {{ background: {fond}; border: 1px solid {couleur};"
                           f" border-left: 6px solid {couleur}; border-radius: 4px; }}"
                           f" QFrame#bandeau QLabel {{ background: transparent; color: {theme.TEXTE}; }}")
        self.__texte.setText(texte)
        self.__texte.setAccessibleName(texte)
        self.show()
        self.__icone.update()
        annoncer(self, texte, assertif)

    def succes(self, message: str, details=()) -> None:
        texte = "OK : " + message + "".join(f"\nRemarque : {d}" for d in details)
        self.__montrer(texte, "ok", theme.SUCCES, theme.FOND_SUCCES, bool(details))

    def refus(self, motif: str) -> None:
        self.__montrer(f"REFUSÉ : {motif}", "refus", theme.ERREUR, theme.FOND_ERREUR, True)

    def information(self, message: str) -> None:
        self.__montrer(message, "info", theme.INFORMATION, theme.FOND_INFO, False)

    def afficher(self, resultat, message_ok: str) -> None:
        """Raccourci pour un Resultat de la couche application."""
        if resultat.ok:
            self.succes(message_ok, resultat.details)
        else:
            self.refus(resultat.motif or "action refusée")


class Champ(QWidget):
    """Etiquette liee au champ (Alt + lettre), aide facultative, message d'erreur sous le champ."""

    def __init__(self, libelle: str, widget: QWidget, aide: str = None, obligatoire: bool = False,
                 parent=None) -> None:
        super().__init__(parent)
        self.widget = widget
        texte = libelle + (" (obligatoire)" if obligatoire else "")
        self.etiquette = QLabel(texte)  # texte du programme : les & servent de lettres d'acces
        self.etiquette.setBuddy(widget)
        self.etiquette.setProperty("role", "titre")
        sans_acces = texte.replace("&", "")
        widget.setAccessibleName(sans_acces)
        self.__erreur = etiquette("", "erreur-champ")
        self.__erreur.hide()
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(4)
        colonne.addWidget(self.etiquette)
        colonne.addWidget(widget)
        if aide:
            self.aide = etiquette(aide, "secondaire")
            widget.setAccessibleDescription(aide)
            colonne.addWidget(self.aide)
        colonne.addWidget(self.__erreur)

    def erreur(self, message: str) -> None:
        self.__erreur.setText(f"Erreur : {message}")
        self.__erreur.show()
        self.widget.setProperty("erreur", True)
        self.widget.setAccessibleDescription(f"Erreur : {message}")
        self.widget.style().unpolish(self.widget)
        self.widget.style().polish(self.widget)

    def effacer_erreur(self) -> None:
        self.__erreur.hide()
        self.widget.setProperty("erreur", False)
        self.widget.style().unpolish(self.widget)
        self.widget.style().polish(self.widget)

    @property
    def message_erreur(self) -> str:
        return self.__erreur.text() if self.__erreur.isVisible() or self.__erreur.text() else ""
