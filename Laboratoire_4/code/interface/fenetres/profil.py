"""F9 Profil : nom, roles et ce qu'ils permettent."""
from PySide6.QtWidgets import QDialog, QListWidget, QVBoxLayout

from ..libelles import PERMISSIONS, roles
from ..widgets import Champ, bouton, etiquette


class FenetreProfil(QDialog):

    def __init__(self, profil, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mon profil")
        self.setMinimumWidth(420)
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(20, 16, 20, 16)
        colonne.setSpacing(10)
        nom = etiquette(profil.nom, "titre")
        police = nom.font()
        police.setPointSizeF(police.pointSizeF() * 1.3)
        nom.setFont(police)
        colonne.addWidget(nom)
        colonne.addWidget(etiquette(f"Compte n° {profil.numero}", "secondaire"))
        colonne.addWidget(etiquette("Rôles : " + roles(profil.roles)))
        droits = QListWidget()
        droits.addItems([PERMISSIONS[p] for p in profil.permissions])
        colonne.addWidget(Champ("&Ce que vos rôles permettent", droits))
        fermer = bouton("&Fermer la fenêtre", role="principal")
        fermer.setDefault(True)
        fermer.clicked.connect(self.accept)
        colonne.addWidget(fermer)
        fermer.setFocus()
