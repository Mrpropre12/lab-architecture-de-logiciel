"""Fichiers de depart deposes dans le dossier de televersement, pour pouvoir joindre des fichiers tout de suite."""
import os
import struct
import zlib

ICI = os.path.dirname(os.path.abspath(__file__))
TELEVERSEMENTS = os.environ.get("TICKETS_UPLOAD_DIR", os.path.join(ICI, "donnees", "televersements"))


def png(largeur, hauteur, rgb):
    """Petite image PNG valide, ecrite sans bibliotheque."""
    def bloc(nature, donnees):
        return struct.pack(">I", len(donnees)) + nature + donnees + struct.pack(">I", zlib.crc32(nature + donnees))
    lignes = b"".join(b"\x00" + bytes(rgb) * largeur for _ in range(hauteur))
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(lignes)) + bloc(b"IEND", b""))


def preparer_fichiers():
    """Fichiers deposes par les utilisateurs dans le dossier de televersement."""
    os.makedirs(TELEVERSEMENTS, exist_ok=True)
    fichiers = {
        "trace.txt": "Traceback (most recent call last):\n  File \"portail.py\", line 42\nKeyError: 'session'".encode("utf-8"),
        "capture.png": png(320, 180, (25, 25, 35)),
        "demo.mp4": b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64,  # en-tete MP4 : la video n'est jamais lue
        "virus.exe": b"MZ\x90\x00",
    }
    for nom, donnees in fichiers.items():
        with open(os.path.join(TELEVERSEMENTS, nom), "wb") as f:
            f.write(donnees)
    print(f"  Fichiers de depart crees dans {TELEVERSEMENTS}")


# ---------------------------------------------------------------- comptes et tickets de depart
# Mots de passe de demonstration (ecrits dans le README) : a ne jamais reutiliser ailleurs.
COMPTES_DEMO = [
    # (nom, courriel, mot de passe, roles en plus de Rapporteur)
    ("Alice", "alice@uqac.ca", "alice-2026", "Administratrice (et Développeuse)"),
    ("Remi", "remi@uqac.ca", "remi-2026", "Rapporteur"),
    ("Rita", "rita@uqac.ca", "rita-2026", "Rapporteuse"),
    ("Diane", "diane@uqac.ca", "diane-2026", "Développeuse"),
    ("Damien", "damien@uqac.ca", "damien-2026", "Développeur"),
]


def creer_systeme():
    """Registres de depart : cinq comptes et deux tickets, partages par la console et l'interface.

    Les comptes sont obtenus par authenticate, comme le ferait n'importe quel client.
    """
    from gestion_tickets.acteurs import DeveloperRole, UserRegistry
    from gestion_tickets.ticket import ContentFactory, Priority, TicketRegistry

    preparer_fichiers()
    (nom_a, mail_a, mdp_a, _), *autres = COMPTES_DEMO
    users = UserRegistry(nom_a, mail_a, mdp_a)
    tickets = TicketRegistry(users)
    for nom, mail, mdp, _ in autres:
        users.register(nom, mail, mdp)
    alice, remi, rita, diane, damien = (users.authenticate(mail, mdp) for _, mail, mdp, _ in COMPTES_DEMO)
    for dev in (diane, damien):
        users.grant_role(alice, dev, DeveloperRole())
    t1 = tickets.create(remi, "Écran noir au démarrage du portail", Priority.HAUTE)
    t1.add_content(remi, ContentFactory.from_path("trace.txt"))
    t1.add_content(remi, ContentFactory.from_path("capture.png"))
    t1.add_comment(remi, "Arrive à chaque redémarrage.")
    t1.assign(diane, damien)
    tickets.create(rita, "Faute dans le menu Aide", Priority.BASSE)
    return users, tickets
