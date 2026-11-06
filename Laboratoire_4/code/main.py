"""Gestionnaire de tickets (6GEI311) : interface graphique PySide6.

Deux facons de lancer, depuis le dossier code :
    python main.py                      autonome, comme au labo 3 (modele dans ce processus)
    python main.py --serveur            client de l'API REST deployee (labo 4)
    python main.py --serveur URL        client d'un autre serveur (ex. http://127.0.0.1:8000)
L'interface est la meme dans les deux cas : seuls les services injectes changent.
La console du labo 2 reste disponible :  python console.py
"""
import argparse
import os
import sys

from donnees_demo import COMPTES_DEMO

SERVEUR_PAR_DEFAUT = os.environ.get("TICKETS_SERVEUR", "https://tickets-6gei311.onrender.com")


def lire_arguments(argv):
    p = argparse.ArgumentParser(description="Gestionnaire de tickets (6GEI311)")
    p.add_argument("--serveur", nargs="?", const=SERVEUR_PAR_DEFAUT, metavar="URL",
                   help=f"utiliser l'API REST (par defaut {SERVEUR_PAR_DEFAUT})")
    return p.parse_known_args(argv)  # les arguments restants vont a Qt


def main(argv=None) -> int:
    arguments, reste = lire_arguments(sys.argv[1:] if argv is None else argv)
    from interface.app import lancer  # Qt n'est charge que pour l'interface graphique
    qt_argv = [sys.argv[0]] + reste
    if arguments.serveur:
        from client import CacheImages, ClientComptes, ClientTickets, Transport
        transport = Transport(arguments.serveur)
        images = CacheImages(transport)
        try:
            return lancer(ClientComptes(transport), ClientTickets(transport, images), COMPTES_DEMO, qt_argv)
        finally:
            images.vider()
            transport.fin()
    from application import creer_application
    from donnees_demo import TELEVERSEMENTS, creer_systeme
    users, tickets = creer_systeme()
    _, comptes, services = creer_application(users, tickets, TELEVERSEMENTS)
    return lancer(comptes, services, COMPTES_DEMO, qt_argv)


if __name__ == "__main__":
    sys.exit(main())
