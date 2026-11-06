"""Les tests de la couche application du labo 3, rejoues a travers l'API REST (labo 4).

Chaque classe herite d'une classe de test_application : memes scenarios, memes motifs
attendus, mais self.comptes et self.tickets sont les clients HTTP (client/), branches sur
le serveur (serveur/) par le TestClient, sans reseau. Si un test passe en local et echoue
ici, le client ou le serveur trahit le contrat.
"""
import os
import sys
import unittest
import warnings
from types import SimpleNamespace
from unittest import mock

import test_application as ta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
import donnees_demo  # noqa: E402
from contrat import BlocImage, Cause, Priority  # noqa: E402

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient
    import httpx
    from client import creer_clients
    from serveur import creer_api
except ImportError:  # sans FastAPI ou httpx, ces tests sont ignores
    TestClient = None

SECRET = "secret-de-test-assez-long-pour-hs256"


class _VueDeSession:
    """Ce que les tests du labo 3 lisent de la Session locale, reconstruit depuis le client."""

    def __init__(self, transport) -> None:
        self.__t = transport

    @property
    def connecte(self):
        p = self.__t.profil if self.__t.connecte else None
        return SimpleNamespace(name=p.nom) if p else None

    def peut(self, permission) -> bool:
        p = self.__t.profil if self.__t.connecte else None
        return p is not None and permission in p.permissions


@unittest.skipIf(TestClient is None, "FastAPI ou httpx absent")
class BaseDistante(ta.Base):

    def setUp(self):
        super().setUp()  # dossiers temporaires et journal, comme en local
        with mock.patch("builtins.print"):
            users, tickets = donnees_demo.creer_systeme()
        self.http = TestClient(creer_api(users, tickets, self.dossier.name, secret=SECRET, web=False))
        self.transport, self.comptes, self.tickets = creer_clients(http=self.http)
        self.session = _VueDeSession(self.transport)


class TestComptesDistants(BaseDistante, ta.TestComptes):
    pass


class TestListesDistantes(BaseDistante, ta.TestListes):
    pass


class TestCycleDeVieDistant(BaseDistante, ta.TestCycleDeVie):
    pass


class TestCreationEtPiecesJointesDistantes(BaseDistante, ta.TestCreationEtPiecesJointes):

    def test_creer_avec_texte_et_image(self):
        """Meme scenario ; seule difference voulue : l'image affichee est la copie du cache du client."""
        self.connecter("rita")
        r = self.tickets.creer("Bouton invisible", Priority.NORMALE, "Etapes :\r\n1. Ouvrir", [self.image()])
        self.assertEqual((r.ok, r.details), (True, ()), r.motif)
        image = next(b for b in self.tickets.detail(r.valeur).valeur.blocs if isinstance(b, BlocImage))
        self.assertEqual((image.largeur, image.hauteur), (40, 30))
        self.assertNotEqual(os.path.dirname(image.chemin), os.path.realpath(self.dossier.name))
        with open(image.chemin, "rb") as f, open(self.image(), "rb") as g:
            self.assertEqual(f.read(), g.read())


@unittest.skipIf(TestClient is None, "FastAPI ou httpx absent")
class TestPannesDuReseau(unittest.TestCase):
    """Ce que le client fait quand le serveur ne repond pas ou repond autre chose que l'API."""

    def client(self, gestionnaire):
        http = httpx.Client(base_url="https://tickets.exemple", transport=httpx.MockTransport(gestionnaire))
        return creer_clients(http=http)

    def test_serveur_injoignable(self):
        def panne(requete):
            raise httpx.ConnectError("refuse", request=requete)
        _, comptes, _ = self.client(panne)
        r = comptes.connecter("alice@uqac.ca", "alice-2026")
        self.assertEqual(r.cause, Cause.INJOIGNABLE)
        self.assertIn("serveur injoignable", r.motif)

    def test_delai_depasse(self):
        def lent(requete):
            raise httpx.ReadTimeout("lent", request=requete)
        _, comptes, _ = self.client(lent)
        r = comptes.reveiller()
        self.assertEqual((r.ok, r.cause), (False, Cause.INJOIGNABLE))
        self.assertIn("ne repond pas", r.motif)

    def test_page_d_attente_de_render(self):
        _, comptes, _ = self.client(lambda requete: httpx.Response(502, text="<html>Service waking up</html>"))
        r = comptes.connecter("alice@uqac.ca", "alice-2026")
        self.assertEqual((r.cause, r.motif), (Cause.INJOIGNABLE, "reponse inattendue du serveur (HTTP 502)"))

    def test_jeton_refuse_deconnecte_le_client(self):
        reponses = iter([
            httpx.Response(201, json={"jeton": "j", "expire_le": "2026-11-06T09:00:00Z",
                                      "profil": {"numero": 1, "nom": "Alice", "roles": ["Rapporteur"],
                                                 "permissions": ["VIEW"]}}),
            httpx.Response(401, json={"motif": "jeton invalide ou expire : reconnectez-vous", "details": [],
                                      "cause": "NON_CONNECTE"}),
        ])
        transport, comptes, tickets = self.client(lambda requete: next(reponses))
        self.assertTrue(comptes.connecter("alice@uqac.ca", "alice-2026").ok)
        r = tickets.lister()
        self.assertEqual((r.cause, transport.connecte), (Cause.NON_CONNECTE, False))
        self.assertEqual(tickets.lister().motif, "aucun compte connecte")  # plus aucune requete envoyee


if __name__ == "__main__":
    unittest.main()
