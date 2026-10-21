"""Lecture du diagramme PlantUML (docs/diagramme_v4.puml) pour les tests de conformite."""
import os
import re

PUML = os.path.join(os.path.dirname(__file__), os.pardir, "docs", "diagramme_v4.puml")

_PKG = re.compile(r'^package\s+"(.*?)"\s*\{$')
_CLS = re.compile(r'^(abstract class|class|enum|interface)\s+(\w+)(?:\s*<<(\w+)>>)?\s*\{$')
_REL = re.compile(r'^\s*(\w+)\s*(?:"[^"]*")?\s*(<\|--|<\|\.\.|<--|-->|o--|\*--|--o|<\.\.|\.\.>)'
                  r'\s*(?:"[^"]*")?\s*(\w+)\s*(?::\s*(.*))?$')


def lire(chemin=PUML):
    """Renvoie (classes, relations). classes[nom] = dict(kind, stereo, body, pkgs)."""
    with open(chemin, encoding="utf-8") as f:
        lignes = f.read().splitlines()
    classes, pile, i = {}, [], 0
    while i < len(lignes):
        s = lignes[i].strip()
        mp, mc = _PKG.match(s), _CLS.match(s)
        if mp:
            pile.append(mp.group(1))
        elif mc:
            kind, nom, stereo = mc.groups()
            corps = []
            i += 1
            while lignes[i].strip() != "}":
                if lignes[i].strip():
                    corps.append(lignes[i].strip())
                i += 1
            classes[nom] = dict(kind=kind, stereo=stereo, body=corps, pkgs=list(pile))
        elif s == "}":
            pile.pop()
        i += 1
    relations = [m.groups() for m in (_REL.match(l) for l in lignes) if m]
    return classes, relations


def snake(nom):
    """camelCase du diagramme vers snake_case PEP 8 (userID -> user_id)."""
    if nom.isupper():
        return nom
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", nom).lower()


class Membre:
    """Un attribut ou une operation du diagramme, traduit en nom Python."""

    def __init__(self, classe, ligne):
        self.classe, self.ligne = classe, ligne
        self.vis = ligne[0]
        reste = ligne[1:].strip()
        self.static = "{static}" in reste
        self.abstract = "{abstract}" in reste
        self.secret = "{secret}" in reste  # attribut sans aucun accesseur (empreintes de mots de passe)
        reste = re.sub(r"\{(abstract|static|secret)\}\s*", "", reste)
        self.operation = "(" in reste
        self.constructeur = "<<create>>" in reste
        tete = reste.split("(")[0] if self.operation else reste.split(":")[0]
        self.nom = tete.replace("<<create>>", "").strip()

    def nom_python(self):
        if self.constructeur:
            return "__init__"
        if self.nom == "equals":
            return "__eq__"
        if self.nom == "hash":
            return "__hash__"
        base = snake(self.nom)
        if self.vis == "+":
            return base
        if self.vis in "~#":
            return "_" + base
        return f"_{self.classe}__{base}"  # prive : nom brouille par Python


def membres(classes, nom):
    return [Membre(nom, l) for l in classes[nom]["body"] if l[0] in "+-#~"]
