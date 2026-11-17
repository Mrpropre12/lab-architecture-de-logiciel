"""Conformite du code au diagramme de classes v4.

Le test relit le .puml et verifie, pour chaque paquetage deja implemente :
classes, nature (interface, abstraite, enum), heritages, operations avec leur
visibilite, accesseurs implicites de la legende, et absence d'API non declaree.
"""
import importlib
import importlib.util
import inspect
import unittest
from enum import Enum

from uml import lire, membres, snake

# Paquetage du diagramme (debut du titre) -> paquet Python. On ajoute une ligne par etape.
PAQUETS = {
    "Qui agit": "gestion_tickets.acteurs",
    "Le ticket": "gestion_tickets.ticket",
    "Consultation": "gestion_tickets.consultation",
    "Application": "application",
    "Interface": "interface",
}
if importlib.util.find_spec("PySide6") is None:  # sans PySide6, le paquetage Interface n'est pas verifie
    del PAQUETS["Interface"]
# Classes du diagramme pas encore programmees. La liste doit etre vide a la remise.
EN_ATTENTE = set()

CLASSES, RELATIONS = lire()


def paquet_python(nom_classe):
    racine = CLASSES[nom_classe]["pkgs"][0]
    return next((mod for titre, mod in PAQUETS.items() if racine.startswith(titre)), None)


IMPLEMENTEES = {c: paquet_python(c) for c in CLASSES if paquet_python(c) and c not in EN_ATTENTE}


def classe_python(nom):
    return getattr(importlib.import_module(IMPLEMENTEES[nom]), nom, None)


class TestConformite(unittest.TestCase):

    def test_au_moins_un_paquetage(self):
        self.assertTrue(IMPLEMENTEES)

    def test_classes_presentes_et_nature(self):
        for nom, info in CLASSES.items():
            if nom not in IMPLEMENTEES:
                continue
            with self.subTest(classe=nom):
                cls = classe_python(nom)
                self.assertIsNotNone(cls, f"{nom} absente de {IMPLEMENTEES[nom]}")
                if info["kind"] == "enum":
                    self.assertTrue(issubclass(cls, Enum))
                    self.assertEqual([m.name for m in cls], info["body"])
                elif info["kind"] in ("interface", "abstract class"):
                    self.assertTrue(inspect.isabstract(cls), f"{nom} doit etre abstraite")
                else:
                    self.assertFalse(inspect.isabstract(cls), f"{nom} doit etre concrete")

    def test_heritages(self):
        for parent, op, enfant, _ in RELATIONS:
            if op in ("<|--", "<|..") and parent in IMPLEMENTEES and enfant in IMPLEMENTEES:
                with self.subTest(relation=f"{enfant} -> {parent}"):
                    self.assertTrue(issubclass(classe_python(enfant), classe_python(parent)))

    def test_operations_et_visibilite(self):
        for nom in IMPLEMENTEES:
            if CLASSES[nom]["kind"] == "enum":
                continue
            cls = classe_python(nom)
            for m in membres(CLASSES, nom):
                if not m.operation:
                    continue
                py = m.nom_python()
                with self.subTest(operation=f"{nom}.{m.nom}", python=py):
                    self.assertIn(py, cls.__dict__, f"{nom} doit definir {py}")
                    attr = cls.__dict__[py]
                    if m.static:
                        self.assertIsInstance(attr, (staticmethod, classmethod))
                    if m.abstract or CLASSES[nom]["kind"] == "interface":
                        self.assertTrue(getattr(attr, "__isabstractmethod__", False),
                                        "operation d'interface ou {abstract} : doit etre abstraite")

    def test_attributs_statiques(self):
        for nom in IMPLEMENTEES:
            for m in membres(CLASSES, nom):
                if m.static and not m.operation:
                    with self.subTest(attribut=f"{nom}.{m.nom}"):
                        self.assertIn(m.nom_python(), classe_python(nom).__dict__)

    def test_accesseurs_implicites_de_la_legende(self):
        """Chaque attribut d'instance a un accesseur public en lecture (propriete),
        sauf s'il est dessine avec une autre visibilite (ex. ~ getEmail) ou marque {secret}."""
        for nom in IMPLEMENTEES:
            if CLASSES[nom]["kind"] == "enum":
                continue
            cls = classe_python(nom)
            if CLASSES[nom]["stereo"] == "dataclass":  # champs publics immuables : pas d'accesseur
                self.assertTrue(getattr(cls, "__dataclass_params__").frozen, f"{nom} doit etre immuable")
                continue
            ops = {m.nom for m in membres(CLASSES, nom) if m.operation}
            for m in membres(CLASSES, nom):
                if m.operation or m.static:
                    continue
                if m.secret:
                    with self.subTest(attribut=f"{nom}.{m.nom}", secret=True):
                        self.assertIsNone(getattr(cls, snake(m.nom), None), "un attribut {secret} n'a aucun accesseur")
                    continue
                cache = "get" + m.nom[0].upper() + m.nom[1:] in ops
                prop = getattr(cls, snake(m.nom), None)
                with self.subTest(attribut=f"{nom}.{m.nom}"):
                    if cache:
                        self.assertNotIsInstance(prop, property, "accesseur public interdit")
                    else:
                        self.assertIsInstance(prop, property, f"propriete {snake(m.nom)} attendue")
                        self.assertIsNone(prop.fset, "accesseur en lecture seulement")

    def test_aucune_api_non_declaree(self):
        """Tout nom public ou de paquetage (un seul _) defini dans la classe vient du diagramme.
        Seule exception : la redefinition d'un nom herite de Qt (paintEvent, sizeHint, staticMetaObject)."""
        for nom in IMPLEMENTEES:
            if CLASSES[nom]["kind"] == "enum":
                continue
            cls = classe_python(nom)
            qt = [b for b in cls.__mro__[1:] if b.__module__.startswith("PySide6")]
            permis = {m.nom_python() for m in membres(CLASSES, nom)}
            permis |= {snake(m.nom) for m in membres(CLASSES, nom) if not m.operation}
            for attr in cls.__dict__:
                if attr.startswith("__") or attr.startswith(f"_{nom}__") or attr == "_abc_impl":
                    continue
                if any(hasattr(b, attr) for b in qt):
                    continue
                with self.subTest(classe=nom, nom_python=attr):
                    self.assertIn(attr, permis, f"{nom}.{attr} n'est pas dans le diagramme")


if __name__ == "__main__":
    unittest.main()
