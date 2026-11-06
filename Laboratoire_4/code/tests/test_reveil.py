"""Interface branchee sur un serveur distant (labo 4) : reveil avant F1, ecran vivant pendant l'attente."""
import os
import sys
import time
import unittest
from unittest import mock

try:
    from PySide6.QtWidgets import QApplication
    import httpx
except ImportError:
    QApplication = None

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


@unittest.skipIf(QApplication is None, "PySide6 ou httpx absent")
class TestReveil(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from interface.app import creer_qapplication
        cls.app = creer_qapplication([])

    def comptes(self, gestionnaire):
        from client import ClientComptes, Transport
        return ClientComptes(Transport(http=httpx.Client(base_url="https://tickets.exemple",
                                                         transport=httpx.MockTransport(gestionnaire))))

    def test_serveur_qui_repond_lentement(self):
        """L'appel bloque un autre fil ; la boucle Qt tourne et la fenetre d'attente apparait."""
        from interface.app import reveiller_serveur

        def lent(requete):
            time.sleep(0.8)
            return httpx.Response(200, json={"etat": "ok", "version": "4.0.0"})
        affichee = []
        with mock.patch("interface.app.QProgressDialog.show", lambda self: affichee.append(True)), \
                mock.patch("interface.app.QMessageBox.warning") as avertir:
            r = reveiller_serveur(self.comptes(lent))
        self.assertTrue(r.ok)
        self.assertEqual(affichee, [True])
        avertir.assert_not_called()

    def test_serveur_absent_averti_sans_bloquer(self):
        from interface.app import reveiller_serveur

        def panne(requete):
            raise httpx.ConnectError("refuse", request=requete)
        with mock.patch("interface.app.QMessageBox.warning") as avertir:
            r = reveiller_serveur(self.comptes(panne))
        self.assertFalse(r.ok)
        avertir.assert_called_once()
        self.assertIn("serveur injoignable", avertir.call_args.args[2])

    def test_services_locaux_sans_reveil(self):
        """Les services locaux n'ont pas de methode reveiller : lancer() ne tente rien."""
        from application import ServiceComptes
        self.assertFalse(hasattr(ServiceComptes, "reveiller"))


class TestPointDEntree(unittest.TestCase):

    def test_arguments(self):
        import main
        self.assertIsNone(main.lire_arguments([])[0].serveur)
        self.assertEqual(main.lire_arguments(["--serveur"])[0].serveur, main.SERVEUR_PAR_DEFAUT)
        args, reste = main.lire_arguments(["--serveur", "http://127.0.0.1:8000", "-platform", "offscreen"])
        self.assertEqual((args.serveur, reste), ("http://127.0.0.1:8000", ["-platform", "offscreen"]))


if __name__ == "__main__":
    unittest.main()
