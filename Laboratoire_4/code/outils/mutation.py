"""Tests de mutation du labo 3 : chaque erreur introduite doit faire echouer au moins un test.

Usage, depuis le dossier code :  python outils/mutation.py [fichier.py ...]
Sans argument, mute le code ajoute au labo 3 : la couche application, l'authentification,
allowed_actions et DescriptionVisitor.

Un mutant est une copie du code ou une seule expression change : == devient !=, < devient >=,
and devient or, True devient False, un entier augmente de 1, un not disparait ou s'ajoute,
un return renvoie None, + devient -. Les tests tournent sur cette copie, dans un dossier
temporaire : le code d'origine n'est jamais modifie.

Premiere passe : les tests rapides, en parallele, arret au premier echec. Les survivants
repassent ensuite les tests restants (console, conformite, architecture), deux a la fois au plus :
la console lance un vrai processus avec le hachage complet, et une machine trop chargee lui
ferait depasser son delai, ce qui compterait le mutant comme detecte a tort. Un mutant qui
survit aux deux passes montre une regle qu'aucun test ne verifie, ou une mutation equivalente.
"""
import ast
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

ICI = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(ICI)

CIBLES = [
    "application/fichiers.py", "application/resultat.py", "application/services.py",
    "application/session.py", "application/vues.py",
    "gestion_tickets/acteurs/utilisateurs.py", "gestion_tickets/ticket/ticket.py",
    "gestion_tickets/consultation/description.py",
]
RAPIDES = ["test_application", "test_authentification", "test_actions_permises", "test_ticket", "test_acteurs",
           "test_revue", "test_description", "test_contenus", "test_consultation", "test_interface"]
LENTS = ["test_console", "test_conformite", "test_architecture"]
TOUS = RAPIDES + LENTS
DELAI = 120  # s ; un mutant qui boucle est compte comme detecte

_COMPARAISONS = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.Gt: ast.LtE,
                 ast.LtE: ast.Gt, ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}
_SYMBOLES = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.GtE: ">=", ast.Gt: ">", ast.LtE: "<=",
             ast.In: "in", ast.NotIn: "not in", ast.Is: "is", ast.IsNot: "is not"}


def _parents(arbre):
    parents = {}
    for noeud in ast.walk(arbre):
        for enfant in ast.iter_child_nodes(noeud):
            parents[enfant] = noeud
    return parents


def _ignore(noeud, parents):
    """Pas de mutation dans un appel au journal (le motif d'un refus n'est pas une regle)."""
    while noeud in parents:
        noeud = parents[noeud]
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute) \
                and isinstance(noeud.func.value, ast.Name) and noeud.func.value.id == "_journal":
            return True
    return False


def points(source):
    """(rang du noeud dans ast.walk, sorte, detail, ligne, description) pour chaque mutation possible."""
    arbre = ast.parse(source)
    parents = _parents(arbre)
    trouves = []
    for rang, n in enumerate(ast.walk(arbre)):
        if _ignore(n, parents):
            continue
        ligne = getattr(n, "lineno", 0)
        if isinstance(n, ast.Compare):
            for j, op in enumerate(n.ops):
                if type(op) in _COMPARAISONS:
                    nouveau = _COMPARAISONS[type(op)]
                    trouves.append((rang, "compare", j, ligne, f"{_SYMBOLES[type(op)]} devient {_SYMBOLES[nouveau]}"))
        elif isinstance(n, ast.BoolOp):
            trouves.append((rang, "boolop", None, ligne, "and devient or" if isinstance(n.op, ast.And)
                            else "or devient and"))
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            trouves.append((rang, "sans_not", None, ligne, "not retire"))
        elif isinstance(n, ast.Constant) and isinstance(n.value, bool):
            trouves.append((rang, "constante", None, ligne, f"{n.value} devient {not n.value}"))
        elif isinstance(n, ast.Constant) and type(n.value) is int:
            trouves.append((rang, "constante", None, ligne, f"{n.value} devient {n.value + 1}"))
        elif isinstance(n, ast.Return) and n.value is not None \
                and not (isinstance(n.value, ast.Constant) and n.value.value is None):
            trouves.append((rang, "return", None, ligne, "renvoie None"))
        elif isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)):
            trouves.append((rang, "binop", None, ligne, "+ devient -" if isinstance(n.op, ast.Add) else "- devient +"))
        if isinstance(n, (ast.If, ast.While, ast.IfExp)) \
                and not isinstance(n.test, (ast.Compare, ast.BoolOp, ast.UnaryOp)):
            trouves.append((rang, "ajout_not", None, n.test.lineno, "condition inversee (not ajoute)"))
    return trouves


def muter(source, rang, sorte, detail):
    """Source du mutant, ou une seule expression a change."""
    arbre = ast.parse(source)
    noeuds = list(ast.walk(arbre))
    n = noeuds[rang]
    if sorte == "compare":
        n.ops[detail] = _COMPARAISONS[type(n.ops[detail])]()
    elif sorte == "boolop":
        n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
    elif sorte == "sans_not":
        parent = _parents(arbre)[n]
        for champ, valeur in ast.iter_fields(parent):
            if valeur is n:
                setattr(parent, champ, n.operand)
            elif isinstance(valeur, list) and n in valeur:
                valeur[valeur.index(n)] = n.operand
    elif sorte == "constante":
        n.value = (not n.value) if isinstance(n.value, bool) else n.value + 1
    elif sorte == "return":
        n.value = ast.Constant(None)
    elif sorte == "binop":
        n.op = ast.Sub() if isinstance(n.op, ast.Add) else ast.Add()
    elif sorte == "ajout_not":
        n.test = ast.UnaryOp(ast.Not(), n.test)
    return ast.unparse(ast.fix_missing_locations(arbre))


def lancer_tests(copie, modules, arret_au_premier=True):
    """True si au moins un test echoue (mutant detecte)."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=os.path.join(copie, "tests"), TICKETS_UPLOAD_DIR=os.path.join(copie, "donnees", "up"))
    commande = [sys.executable, "-m", "unittest"] + (["-f"] if arret_au_premier else []) + modules
    try:
        r = subprocess.run(commande, cwd=copie, env=env, capture_output=True, timeout=DELAI)
    except subprocess.TimeoutExpired:
        return True
    return r.returncode != 0


def copier(destination):
    shutil.copytree(CODE, destination, ignore=shutil.ignore_patterns("__pycache__", "donnees", "captures", "*.png"))


def main(cibles):
    debut = time.time()
    travail = tempfile.mkdtemp(prefix="mutation_")
    copies = queue.Queue()
    nb = max(2, (os.cpu_count() or 4) - 1)
    for i in range(nb):
        copie = os.path.join(travail, f"copie{i}")
        copier(copie)
        copies.put(copie)
    try:
        temoin = copies.get()
        if lancer_tests(temoin, TOUS, arret_au_premier=False):
            print("La suite de tests echoue deja sans mutation : rien a mesurer.")
            return 2
        copies.put(temoin)

        mutants = []
        for cible in cibles:
            with open(os.path.join(CODE, cible), encoding="utf-8") as f:
                source = f.read()
            lignes = source.splitlines()
            for rang, sorte, detail, ligne, description in points(source):
                mutants.append((cible, source, rang, sorte, detail, ligne, description, lignes[ligne - 1].strip()))

        def essayer(mutant, modules, arret):
            cible, source, rang, sorte, detail = mutant[:5]
            copie = copies.get()
            chemin = os.path.join(copie, cible)
            try:
                with open(chemin, "w", encoding="utf-8") as f:
                    f.write(muter(source, rang, sorte, detail))
                return lancer_tests(copie, modules, arret)
            finally:
                with open(chemin, "w", encoding="utf-8") as f:
                    f.write(source)
                copies.put(copie)

        with ThreadPoolExecutor(nb) as pool:
            detectes = list(pool.map(lambda m: essayer(m, RAPIDES, True), mutants))
        restants = [m for m, d in zip(mutants, detectes) if not d]
        with ThreadPoolExecutor(min(2, nb)) as pool:
            survivants = [m for m, d in zip(restants, pool.map(lambda m: essayer(m, LENTS, False), restants)) if not d]
    finally:
        shutil.rmtree(travail, ignore_errors=True)

    print(f"{'Fichier':48} {'mutants':>8} {'detectes':>9} {'survivants':>11}")
    for cible in cibles:
        total = sum(1 for m in mutants if m[0] == cible)
        restes = sum(1 for m in survivants if m[0] == cible)
        print(f"{cible:48} {total:8} {total - restes:9} {restes:11}")
    total = len(mutants)
    print(f"{'Total':48} {total:8} {total - len(survivants):9} {len(survivants):11}"
          f"   ({(total - len(survivants)) / total:.1%} detectes, {time.time() - debut:.0f} s)")
    for cible, _, _, _, _, ligne, description, texte in survivants:
        print(f"  survivant  {cible}:{ligne}  {description}  |  {texte}")
    return 1 if survivants else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or CIBLES))
