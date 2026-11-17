"""Jetons de couleur et feuille de style : le seul endroit ou une couleur est ecrite.

Palette validee : chaque couleur de texte atteint
au moins 4,5:1 sur blanc, chaque bordure ou indicateur au moins 3:1 (WCAG 2.2 AA,
criteres 1.4.3 et 1.4.11). Changer de palette, ou ajouter un theme sombre, ne
touche que ce fichier.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

from application import Priority, Status

# ---------------------------------------------------------------- les onze jetons
TEXTE = "#242424"            # Fluent 2 grey[14]          15,5:1
TEXTE_SECONDAIRE = "#484949"  # GOV.UK                      9,0:1
GRIS_MINIMAL = "#757575"     # USWDS gray-50 : bordures      4,6:1
SEPARATEUR = "#cecece"       # GOV.UK : decoratif seulement  1,6:1
FOND = "#ffffff"
ACCENT = "#0f62fe"           # IBM Carbon Blue 60 : accent et focus  5,0:1
INFORMATION = "#0043ce"      # Carbon Blue 70                7,8:1
SUCCES = "#0f7a52"           # GOV.UK                        5,4:1
ERREUR = "#da1e28"           # Carbon Red 60                 5,0:1
AVERTISSEMENT_TEXTE = "#936f38"  # USWDS gold-50v            4,6:1
AVERTISSEMENT_FOND = "#f1c21b"   # Carbon Yellow 30, toujours avec TEXTE_SUR_JAUNE
TEXTE_SUR_JAUNE = "#161616"  # 10,8:1 sur AVERTISSEMENT_FOND

# Fonds pales des bandeaux (le texte reste TEXTE : 14:1 ou plus)
FOND_SUCCES = "#e6f4ea"
FOND_ERREUR = "#fdecea"
FOND_INFO = "#edf5ff"
FOND_ZONE = "#f4f4f4"        # fond des zones de lecture

# ---------------------------------------------------------------- statuts et priorites
# (libelle affiche, couleur de la pastille, couleur du texte dessus, icone)
STATUTS = {
    Status.OUVERT: ("OUVERT", SUCCES, FOND, "cercle"),
    Status.ASSIGNE: ("ASSIGNÉ", ACCENT, FOND, "personne"),
    Status.VALIDATION: ("VALIDATION", AVERTISSEMENT_FOND, TEXTE_SUR_JAUNE, "sablier"),
    Status.TERMINE: ("TERMINÉ", "#6929c4", FOND, "coche"),
    Status.FERME: ("FERMÉ", TEXTE_SECONDAIRE, FOND, "barre"),
}
PRIORITES = {
    Priority.BASSE: ("BASSE", TEXTE_SECONDAIRE, FOND, "1"),
    Priority.NORMALE: ("NORMALE", INFORMATION, FOND, "2"),
    Priority.HAUTE: ("HAUTE", "#b50909", FOND, "3"),
}

# ---------------------------------------------------------------- tailles
CIBLE_MIN = 32               # px : boutons et champs (WCAG 2.5.8 exige 24)
FOCUS = 2                    # px : epaisseur de l'indicateur de focus
ECHELLES = (100, 125, 150, 200)  # tailles du texte proposees (WCAG 1.4.4)


def contraste_eleve() -> bool:
    """Vrai si Windows (ou le systeme) est en mode de contraste eleve."""
    hints = QGuiApplication.styleHints()
    try:
        return hints.accessibility().contrastPreference() == Qt.ContrastPreference.HighContrast
    except AttributeError:  # Qt plus ancien que 6.10
        return False


def feuille_de_style() -> str:
    """Bordures d'au moins 3:1, focus de 2 px ACCENT sur chaque type de widget, cibles de 32 px."""
    return f"""
    QWidget {{ color: {TEXTE}; background: {FOND}; }}
    QToolTip {{ color: {TEXTE}; background: {FOND}; border: 1px solid {GRIS_MINIMAL}; }}
    QLabel[role="secondaire"] {{ color: {TEXTE_SECONDAIRE}; }}
    QLabel[role="erreur-champ"] {{ color: {ERREUR}; }}
    QLabel[role="titre"] {{ font-weight: 600; }}

    QPushButton {{
        min-height: {CIBLE_MIN - 2 * FOCUS}px; padding: 0 14px;
        border: {FOCUS}px solid {GRIS_MINIMAL}; border-radius: 4px; background: {FOND}; color: {TEXTE};
    }}
    QPushButton:hover {{ background: {FOND_ZONE}; }}
    QPushButton:pressed {{ background: {SEPARATEUR}; }}
    QPushButton[role="principal"] {{ background: {ACCENT}; color: {FOND}; border-color: {ACCENT}; }}
    QPushButton[role="principal"]:hover {{ background: {INFORMATION}; border-color: {INFORMATION}; }}
    QPushButton[role="danger"] {{ color: {ERREUR}; border-color: {ERREUR}; }}
    QPushButton:disabled {{ color: {GRIS_MINIMAL}; border-color: {SEPARATEUR}; background: {FOND_ZONE}; }}
    QPushButton:focus {{ border: {FOCUS}px solid {ACCENT}; outline: none; }}
    QPushButton[role="principal"]:focus {{ border: {FOCUS}px solid {TEXTE}; }}

    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
        min-height: {CIBLE_MIN - 2 * FOCUS}px; padding: 0 6px;
        border: 1px solid {GRIS_MINIMAL}; border-radius: 4px; background: {FOND};
        selection-background-color: {ACCENT}; selection-color: {FOND};
    }}
    QPlainTextEdit, QTextEdit {{ padding: 4px 6px; }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: {FOCUS}px solid {ACCENT};
    }}
    QLineEdit[erreur="true"], QPlainTextEdit[erreur="true"] {{ border: {FOCUS}px solid {ERREUR}; }}
    QComboBox QAbstractItemView {{ selection-background-color: {ACCENT}; selection-color: {FOND}; }}

    QCheckBox, QRadioButton {{ min-height: {CIBLE_MIN - 2 * FOCUS}px; spacing: 8px; padding: 0 4px;
                               border: {FOCUS}px solid transparent; border-radius: 4px; }}
    QCheckBox:focus, QRadioButton:focus {{ border: {FOCUS}px solid {ACCENT}; }}
    QCheckBox::indicator, QRadioButton::indicator {{ width: 18px; height: 18px; }}

    QTableView, QListWidget, QTreeView {{
        border: 1px solid {GRIS_MINIMAL}; gridline-color: {SEPARATEUR};
        selection-background-color: {ACCENT}; selection-color: {FOND};
        alternate-background-color: {FOND_ZONE};
    }}
    QTableView:focus, QListWidget:focus, QTreeView:focus {{ border: {FOCUS}px solid {ACCENT}; }}
    QHeaderView::section {{
        background: {FOND_ZONE}; color: {TEXTE}; font-weight: 600; padding: 6px;
        border: none; border-bottom: 1px solid {GRIS_MINIMAL}; border-right: 1px solid {SEPARATEUR};
    }}

    QTabWidget::pane {{ border: 1px solid {GRIS_MINIMAL}; top: -1px; }}
    QTabBar::tab {{
        min-height: {CIBLE_MIN - 4}px; padding: 0 16px; color: {TEXTE_SECONDAIRE};
        border: 1px solid {SEPARATEUR}; border-bottom: none; background: {FOND_ZONE};
    }}
    QTabBar::tab:selected {{ color: {TEXTE}; background: {FOND}; border-color: {GRIS_MINIMAL};
                             border-top: 3px solid {ACCENT}; font-weight: 600; }}
    QTabBar::tab:focus {{ border: {FOCUS}px solid {ACCENT}; }}

    QMenuBar {{ background: {FOND}; border-bottom: 1px solid {SEPARATEUR}; }}
    QMenuBar::item {{ padding: 6px 10px; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background: {ACCENT}; color: {FOND}; }}
    QMenu {{ border: 1px solid {GRIS_MINIMAL}; }}
    QMenu::item {{ padding: 6px 24px 6px 12px; }}
    QStatusBar {{ background: {FOND_ZONE}; color: {TEXTE_SECONDAIRE}; border-top: 1px solid {SEPARATEUR}; }}
    QStatusBar QLabel {{ background: transparent; color: {TEXTE_SECONDAIRE}; padding: 2px 8px; }}
    QScrollArea {{ border: none; }}
    QFrame[role="zone"] {{ background: {FOND_ZONE}; border: 1px solid {SEPARATEUR}; border-radius: 6px; }}
    QFrame[role="zone"] QLabel {{ background: transparent; }}
    """


def appliquer(app: QApplication) -> bool:
    """Applique le theme clair et renvoie True, sauf en contraste eleve : on garde alors
    le style et la palette du systeme, sans aucune couleur a nous, et on renvoie False."""
    if contraste_eleve():
        return False
    try:
        QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Light)  # theme clair fixe
    except AttributeError:
        pass
    app.setStyle(QStyleFactory.create("Fusion"))
    palette = QPalette()
    for role, couleur in ((QPalette.Window, FOND), (QPalette.Base, FOND), (QPalette.AlternateBase, FOND_ZONE),
                          (QPalette.Text, TEXTE), (QPalette.WindowText, TEXTE), (QPalette.ButtonText, TEXTE),
                          (QPalette.Button, FOND), (QPalette.Highlight, ACCENT), (QPalette.HighlightedText, FOND),
                          (QPalette.ToolTipBase, FOND), (QPalette.ToolTipText, TEXTE),
                          (QPalette.PlaceholderText, GRIS_MINIMAL), (QPalette.Link, ACCENT)):
        palette.setColor(role, QColor(couleur))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(GRIS_MINIMAL))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(GRIS_MINIMAL))
    app.setPalette(palette)
    app.setStyleSheet(feuille_de_style())
    return True


class TailleDuTexte:
    """Taille du texte de 100 % a 200 % (WCAG 1.4.4), a partir de la police du systeme."""

    def __init__(self, app: QApplication) -> None:
        self.__app = app
        self.__base = QFont(app.font())
        self.__echelle = 100

    @property
    def echelle(self) -> int:
        return self.__echelle

    def regler(self, pourcentage: int) -> None:
        self.__echelle = pourcentage
        police = QFont(self.__base)
        taille = self.__base.pointSizeF() if self.__base.pointSizeF() > 0 else 10.0
        police.setPointSizeF(taille * pourcentage / 100)
        self.__app.setFont(police)
        # la feuille de style fige certaines polices : on la reapplique pour suivre la nouvelle taille
        feuille = self.__app.styleSheet()
        if feuille:
            self.__app.setStyleSheet(feuille)

    def plus(self) -> None:
        suivantes = [e for e in ECHELLES if e > self.__echelle]
        if suivantes:
            self.regler(suivantes[0])

    def moins(self) -> None:
        precedentes = [e for e in ECHELLES if e < self.__echelle]
        if precedentes:
            self.regler(precedentes[-1])
