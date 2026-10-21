"""Sens des dependances entre paquets : consultation -> ticket -> acteurs, jamais l'inverse."""
import ast
import os
import unittest

RACINE = os.path.join(os.path.dirname(__file__), os.pardir, "gestion_tickets")
COUCHES = ["acteurs", "ticket", "consultation"]  # de la plus basse a la plus haute


def imports_internes(chemin, paquet):
    """Sous-paquets de gestion_tickets importes par un module."""
    with open(chemin, encoding="utf-8") as f:
        arbre = ast.parse(f.read())
    trouves = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            if noeud.level == 0 and noeud.module and noeud.module.startswith("gestion_tickets."):
                trouves.add(noeud.module.split(".")[1])
            elif noeud.level == 2 and noeud.module:
                trouves.add(noeud.module.split(".")[0])
            elif noeud.level == 1:
                trouves.add(paquet)
        elif isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if alias.name.startswith("gestion_tickets."):
                    trouves.add(alias.name.split(".")[1])
    return trouves


class TestArchitecture(unittest.TestCase):

    def test_dependances_vers_le_bas_seulement(self):
        for paquet in COUCHES:
            dossier = os.path.join(RACINE, paquet)
            if not os.path.isdir(dossier):
                continue
            permis = set(COUCHES[:COUCHES.index(paquet) + 1])
            for racine, _, fichiers in os.walk(dossier):
                for f in fichiers:
                    if f.endswith(".py"):
                        chemin = os.path.join(racine, f)
                        with self.subTest(module=os.path.relpath(chemin, RACINE)):
                            interdits = {i for i in imports_internes(chemin, paquet) - permis
                                         if not i.startswith("_")}  # modules utilitaires communs
                            self.assertFalse(interdits, f"importe une couche superieure : {interdits}")


if __name__ == "__main__":
    unittest.main()
