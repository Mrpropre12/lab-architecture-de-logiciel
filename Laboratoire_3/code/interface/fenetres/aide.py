"""F10 Aide et accessibilite : raccourcis, legende des pastilles, taille du texte, comptes de demonstration.
Toujours au meme endroit : menu Aide, touche F1 (WCAG 3.2.6)."""
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QGridLayout, QHeaderView, QScrollArea, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from application import Priority, Status

from ..widgets import Pastille, bouton, etiquette

RACCOURCIS = [
    ("Tab, Maj + Tab", "Passer au contrôle suivant ou précédent"),
    ("Flèches", "Se déplacer dans une liste ou un tableau"),
    ("Entrée", "Ouvrir le ticket sélectionné, valider un dialogue"),
    ("Échap", "Annuler ou fermer le dialogue"),
    ("Alt + lettre soulignée", "Aller au champ ou au bouton correspondant"),
    ("Ctrl + N", "Nouveau ticket"),
    ("Ctrl + O", "Ouvrir le ticket sélectionné"),
    ("F5", "Actualiser la liste"),
    ("Ctrl + +, Ctrl + -", "Agrandir ou réduire le texte (100 % à 200 %)"),
    ("F1", "Cette aide"),
    ("Ctrl + Q", "Quitter"),
]


def _tableau(nom: str, entetes, lignes) -> QTableWidget:
    t = QTableWidget(len(lignes), len(entetes))
    t.setAccessibleName(nom)
    t.setHorizontalHeaderLabels(entetes)
    t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setTabKeyNavigation(False)
    for i, ligne in enumerate(lignes):
        for j, v in enumerate(ligne):
            t.setItem(i, j, QTableWidgetItem(v))
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.resizeRowsToContents()
    t.setMinimumHeight(t.verticalHeader().length() + t.horizontalHeader().height() + 6)
    return t


class FenetreAide(QDialog):

    def __init__(self, comptes_demo=(), parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aide et accessibilité")
        self.resize(640, 640)
        contenu = QWidget()
        c = QVBoxLayout(contenu)
        c.setSpacing(10)
        c.addWidget(etiquette("Raccourcis clavier", "titre"))
        c.addWidget(_tableau("Raccourcis clavier", ["Touches", "Effet"], RACCOURCIS))

        c.addWidget(etiquette("Légende des pastilles", "titre"))
        c.addWidget(etiquette("La couleur n'est jamais le seul repère : chaque pastille porte aussi son nom "
                              "et une icône de forme différente.", "secondaire"))
        grille = QGridLayout()
        for i, s in enumerate(Status):
            grille.addWidget(Pastille(s), i // 3, i % 3)
        for i, p in enumerate(Priority):
            grille.addWidget(Pastille(p), 2, i)
        c.addLayout(grille)

        c.addWidget(etiquette("Accessibilité", "titre"))
        c.addWidget(etiquette(
            "Toutes les actions se font au clavier. Le résultat de chaque action (OK ou REFUSÉ avec son motif) "
            "s'affiche en haut de la fenêtre et est lu par le lecteur d'écran (NVDA, Narrateur). La taille du "
            "texte se règle dans le menu Affichage, de 100 % à 200 %. En mode de contraste élevé de Windows, "
            "l'application utilise les couleurs du système. Un bouton grisé signifie que l'action n'est pas "
            "possible maintenant ; la ligne « Possible maintenant » de la fiche d'un ticket les énumère."))
        if comptes_demo:
            c.addWidget(etiquette("Comptes de démonstration", "titre"))
            c.addWidget(_tableau("Comptes de démonstration", ["Courriel", "Mot de passe", "Rôles"],
                                 [(courriel, mdp, roles) for _, courriel, mdp, roles in comptes_demo]))
        c.addStretch(1)
        defilement = QScrollArea()
        defilement.setAccessibleName("Contenu de l'aide")
        defilement.setWidgetResizable(True)
        defilement.setWidget(contenu)
        fermer = bouton("&Fermer la fenêtre", role="principal")
        fermer.setDefault(True)
        fermer.clicked.connect(self.accept)
        colonne = QVBoxLayout(self)
        colonne.addWidget(defilement, 1)
        colonne.addWidget(fermer)
        fermer.setFocus()
