"""Gestionnaire de tickets (laboratoire 3, 6GEI311) : interface graphique PySide6.

Assemble les trois couches : le modele du labo 2 (gestion_tickets) avec ses donnees
de depart, la couche application (services sans Qt), puis l'interface graphique.

Lancement, depuis le dossier code :  python main.py
La console du labo 2 reste disponible :  python console.py
"""
import sys

from application import creer_application
from donnees_demo import COMPTES_DEMO, TELEVERSEMENTS, creer_systeme


def main(argv=None) -> int:
    from interface.app import lancer  # Qt n'est charge que pour l'interface graphique
    users, tickets = creer_systeme()
    _, comptes, services = creer_application(users, tickets, TELEVERSEMENTS)
    return lancer(comptes, services, COMPTES_DEMO, argv)


if __name__ == "__main__":
    sys.exit(main())
