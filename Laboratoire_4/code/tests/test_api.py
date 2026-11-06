"""Serveur REST (labo 4) : chaque ressource, chaque code de reponse, sans reseau (TestClient)."""
import logging
import os
import sys
import tempfile
import time
import unittest
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest import mock

import aide  # noqa: F401  (cout de hachage reduit pour les tests)
from gestion_tickets.ticket import ContentFactory, Ticket

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
import donnees_demo  # noqa: E402

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient
    from serveur import creer_api
    from serveur.securite import Jetons
except ImportError:  # sans FastAPI, les tests du serveur sont ignores
    TestClient = None

API = "/api/v1"
SECRET = "secret-de-test-assez-long-pour-hs256"


def creer_client_de_test(test):
    """Systeme de demonstration dans un dossier temporaire, et un TestClient sur l'API."""
    dossier = tempfile.TemporaryDirectory()
    test.addCleanup(dossier.cleanup)
    for cible, valeur in ((ContentFactory, ("_ContentFactory__UPLOAD_DIR", dossier.name)),
                          (donnees_demo, ("TELEVERSEMENTS", dossier.name))):
        p = mock.patch.object(cible, *valeur)
        p.start()
        test.addCleanup(p.stop)
    with mock.patch("builtins.print"):
        users, tickets = donnees_demo.creer_systeme()
    app = creer_api(users, tickets, dossier.name, secret=SECRET, web=False)
    niveau = logging.root.manager.disable  # les motifs de refus passent par le journal du modele
    logging.disable(logging.NOTSET)
    test.addCleanup(logging.disable, niveau)
    return TestClient(app), app


@unittest.skipIf(TestClient is None, "FastAPI absent")
class Base(unittest.TestCase):

    def setUp(self):
        self.http, self.app = creer_client_de_test(self)

    def jeton(self, prenom):
        r = self.http.post(f"{API}/sessions", json={"courriel": f"{prenom}@uqac.ca", "mot_de_passe": f"{prenom}-2026"})
        self.assertEqual(r.status_code, 201, r.text)
        return {"Authorization": f"Bearer {r.json()['jeton']}"}

    def refus(self, reponse, code, cause):
        """Toutes les erreurs ont la meme forme : {motif, details, cause}."""
        self.assertEqual(reponse.status_code, code, reponse.text)
        corps = reponse.json()
        self.assertEqual(set(corps), {"motif", "details", "cause"})
        self.assertEqual(corps["cause"], cause)
        self.assertTrue(corps["motif"])
        return corps["motif"]


class TestSessions(Base):

    def test_sante_sans_jeton(self):
        r = self.http.get(f"{API}/sante")
        self.assertEqual((r.status_code, r.json()["etat"]), (200, "ok"))

    def test_connexion_donne_un_jeton_et_le_profil(self):
        r = self.http.post(f"{API}/sessions", json={"courriel": "alice@uqac.ca", "mot_de_passe": "alice-2026"})
        self.assertEqual(r.status_code, 201)
        corps = r.json()
        self.assertEqual(corps["type"], "bearer")
        self.assertEqual(corps["profil"]["roles"], ["Rapporteur", "Developpeur", "Administrateur"])
        self.assertIn("MANAGE_USERS", corps["profil"]["permissions"])

    def test_mauvais_mot_de_passe(self):
        r = self.http.post(f"{API}/sessions", json={"courriel": "alice@uqac.ca", "mot_de_passe": "faux-faux"})
        self.assertEqual(self.refus(r, 401, "NON_CONNECTE"), "courriel ou mot de passe incorrect")
        self.assertEqual(r.headers["WWW-Authenticate"], "Bearer")

    def test_moi(self):
        r = self.http.get(f"{API}/moi", headers=self.jeton("remi"))
        self.assertEqual((r.status_code, r.json()["nom"]), (200, "Remi"))

    def test_jeton_absent_falsifie_ou_expire(self):
        self.refus(self.http.get(f"{API}/moi"), 401, "NON_CONNECTE")
        self.refus(self.http.get(f"{API}/moi", headers={"Authorization": "Bearer abc.def.ghi"}), 401, "NON_CONNECTE")
        autre = Jetons("un-autre-secret-de-trente-deux-octets").emettre(2)[0]  # signe par un autre serveur
        self.refus(self.http.get(f"{API}/moi", headers={"Authorization": f"Bearer {autre}"}), 401, "NON_CONNECTE")
        self.jeton("remi")
        expire = Jetons(SECRET, timedelta(seconds=-1)).emettre(2)[0]
        self.refus(self.http.get(f"{API}/moi", headers={"Authorization": f"Bearer {expire}"}), 401, "NON_CONNECTE")

    def test_jeton_d_un_compte_desactive(self):
        rita = self.jeton("rita")
        r = self.http.patch(f"{API}/comptes/3", json={"actif": False}, headers=self.jeton("alice"))
        self.assertEqual((r.status_code, r.json()["nom"]), (200, "Rita"))
        self.refus(self.http.get(f"{API}/moi", headers=rita), 401, "NON_CONNECTE")


class TestComptes(Base):

    def test_inscription(self):
        corps = {"nom": "Nina", "courriel": "nina@uqac.ca", "mot_de_passe": "nina-2026", "confirmation": "nina-2026"}
        r = self.http.post(f"{API}/comptes", json=corps)
        self.assertEqual((r.status_code, r.json()["nom"]), (201, "Nina"))
        self.assertIn("deja utilise", self.refus(self.http.post(f"{API}/comptes", json=corps), 422, "INVALIDE"))
        corps["confirmation"] = "autre"
        self.refus(self.http.post(f"{API}/comptes", json=corps), 422, "INVALIDE")

    def test_lister_exige_manage_users(self):
        self.refus(self.http.get(f"{API}/comptes", headers=self.jeton("remi")), 403, "INTERDIT")
        r = self.http.get(f"{API}/comptes", headers=self.jeton("alice"))
        self.assertEqual([c["nom"] for c in r.json()], ["Alice", "Remi", "Rita", "Diane", "Damien"])

    def test_assignables_pour_tout_compte(self):
        r = self.http.get(f"{API}/comptes", params={"assignables": "true"}, headers=self.jeton("remi"))
        self.assertEqual([c["nom"] for c in r.json()], ["Alice", "Diane", "Damien"])

    def test_roles(self):
        alice = self.jeton("alice")
        r = self.http.post(f"{API}/comptes/2/roles", json={"role": "Developpeur"}, headers=alice)
        self.assertEqual(r.status_code, 201)
        self.assertIn("deja le role", self.refus(
            self.http.post(f"{API}/comptes/2/roles", json={"role": "Developpeur"}, headers=alice), 409, "CONFLIT"))
        self.assertEqual(self.http.delete(f"{API}/comptes/2/roles/Developpeur", headers=alice).status_code, 204)
        self.refus(self.http.delete(f"{API}/comptes/2/roles/Rapporteur", headers=alice), 409, "CONFLIT")
        self.refus(self.http.delete(f"{API}/comptes/2/roles/Pirate", headers=alice), 422, "INVALIDE")
        self.refus(self.http.post(f"{API}/comptes/2/roles", json={"role": "Pirate"}, headers=alice), 422, "INVALIDE")
        self.refus(self.http.post(f"{API}/comptes/99/roles", json={"role": "Developpeur"}, headers=alice),
                   404, "INTROUVABLE")
        self.refus(self.http.post(f"{API}/comptes/3/roles", json={"role": "Developpeur"}, headers=self.jeton("remi")),
                   403, "INTERDIT")


class TestTickets(Base):

    def test_visibilite_d_un_rapporteur(self):
        remi = self.jeton("remi")
        r = self.http.get(f"{API}/tickets", headers=remi)
        self.assertEqual([t["numero"] for t in r.json()], [1])
        self.refus(self.http.get(f"{API}/tickets", params={"filtre": "tous"}, headers=remi), 403, "INTERDIT")
        self.refus(self.http.get(f"{API}/tickets/2", headers=remi), 404, "INTROUVABLE")  # existe, mais invisible
        self.refus(self.http.get(f"{API}/tickets/99", headers=remi), 404, "INTROUVABLE")

    def test_filtres_en_query(self):
        diane = self.jeton("diane")
        r = self.http.get(f"{API}/tickets", params={"filtre": "tous", "priorite": "BASSE"}, headers=diane)
        self.assertEqual([t["numero"] for t in r.json()], [2])
        r = self.http.get(f"{API}/tickets", params={"filtre": "tous", "statut": "ASSIGNE"}, headers=diane)
        self.assertEqual([t["numero"] for t in r.json()], [1])
        self.refus(self.http.get(f"{API}/tickets", params={"filtre": "nimporte"}, headers=diane), 422, "INVALIDE")

    def test_creer(self):
        remi = self.jeton("remi")
        r = self.http.post(f"{API}/tickets", json={"titre": "Panne", "priorite": "HAUTE", "texte": "Rien ne va"},
                           headers=remi)
        self.assertEqual((r.status_code, r.json()), (201, {"numero": 3, "details": []}))
        self.assertEqual(r.headers["Location"], f"{API}/tickets/3")
        blocs = self.http.get(r.headers["Location"], headers=remi).json()["blocs"]
        self.assertEqual([b["type"] for b in blocs], ["ticket", "texte"])
        self.assertEqual(blocs[1]["texte"].strip(), "Rien ne va")

    def test_creer_refuse(self):
        remi = self.jeton("remi")
        self.refus(self.http.post(f"{API}/tickets", json={"titre": "   "}, headers=remi), 422, "INVALIDE")
        self.refus(self.http.post(f"{API}/tickets", json={"titre": "X", "priorite": "URGENTE"}, headers=remi),
                   422, "INVALIDE")
        self.refus(self.http.post(f"{API}/tickets", json={"priorite": "HAUTE"}, headers=remi), 422, "INVALIDE")

    def test_detail_et_actions_permises(self):
        d = self.http.get(f"{API}/tickets/1", headers=self.jeton("damien")).json()
        self.assertEqual([b["type"] for b in d["blocs"]], ["ticket", "texte", "image", "commentaire"])
        self.assertIn("SUBMIT", d["actions"])
        self.assertNotIn("VALIDATE", d["actions"])
        self.assertNotIn("chemin", d["blocs"][2])  # aucun chemin du disque du serveur
        self.assertIn("Ticket 1", d["texte"])

    def test_modifier_titre_et_priorite(self):
        r = self.http.patch(f"{API}/tickets/1", json={"titre": "Ecran noir"}, headers=self.jeton("remi"))
        self.assertEqual((r.status_code, r.json()["blocs"][0]["titre"]), (200, "Ecran noir"))
        self.refus(self.http.patch(f"{API}/tickets/1", json={"priorite": "BASSE"}, headers=self.jeton("remi")),
                   403, "INTERDIT")  # SET_PRIORITY : administrateur seulement
        self.refus(self.http.patch(f"{API}/tickets/1", json={"titre": "Autre"}, headers=self.jeton("diane")),
                   409, "CONFLIT")  # EDIT accorde par les roles, mais diane n'est pas l'auteur
        r = self.http.patch(f"{API}/tickets/1", json={"priorite": "BASSE"}, headers=self.jeton("alice"))
        self.assertEqual(r.json()["blocs"][0]["priorite"], "BASSE")
        self.refus(self.http.patch(f"{API}/tickets/1", json={}, headers=self.jeton("alice")), 422, "INVALIDE")


class TestCycleDeVie(Base):

    def transition(self, prenom, action, **corps):
        return self.http.post(f"{API}/tickets/1/transitions", json={"action": action, **corps},
                              headers=self.jeton(prenom))

    def test_parcours_complet(self):
        self.refus(self.transition("diane", "valider"), 409, "CONFLIT")  # encore ASSIGNE
        r = self.transition("damien", "soumettre")
        self.assertEqual((r.status_code, r.json()), (201, {"action": "soumettre", "statut": "VALIDATION"}))
        self.refus(self.transition("diane", "rejeter"), 422, "INVALIDE")  # motif exige
        r = self.transition("diane", "rejeter", motif="tests manquants")
        self.assertEqual(r.json()["statut"], "ASSIGNE")
        self.transition("damien", "soumettre")
        self.assertEqual(self.transition("diane", "valider").json()["statut"], "TERMINE")
        self.refus(self.transition("diane", "fermer", motif="livre"), 409, "CONFLIT")  # TERMINE est final
        self.refus(self.transition("diane", "rouvrir", motif="regression"), 403, "INTERDIT")
        self.assertEqual(self.transition("alice", "rouvrir", motif="regression").json()["statut"], "OUVERT")
        self.assertEqual(self.transition("diane", "fermer", motif="doublon").json()["statut"], "FERME")

    def test_assigner(self):
        self.refus(self.http.post(f"{API}/tickets/2/transitions", json={"action": "assigner"},
                                  headers=self.jeton("diane")), 422, "INVALIDE")
        r = self.http.post(f"{API}/tickets/2/transitions", json={"action": "assigner", "assigne": 4},
                           headers=self.jeton("diane"))
        self.assertEqual(r.json(), {"action": "assigner", "statut": "ASSIGNE"})
        self.refus(self.http.post(f"{API}/tickets/2/transitions", json={"action": "detruire"},
                                  headers=self.jeton("diane")), 422, "INVALIDE")


class TestDescription(Base):

    def test_ajouter_un_texte(self):
        r = self.http.post(f"{API}/tickets/1/textes", json={"texte": "Aussi sous Firefox"}, headers=self.jeton("remi"))
        self.assertEqual((r.status_code, r.json()["texte"].strip()), (201, "Aussi sous Firefox"))
        self.refus(self.http.post(f"{API}/tickets/1/textes", json={"texte": "x"}, headers=self.jeton("diane")),
                   409, "CONFLIT")
        self.refus(self.http.post(f"{API}/tickets/1/textes", json={"texte": "  "}, headers=self.jeton("remi")),
                   422, "INVALIDE")
        types = [b["type"] for b in self.http.get(f"{API}/tickets/1/contenus", headers=self.jeton("remi")).json()]
        self.assertEqual(types, ["texte", "image", "texte"])

    def test_joindre_puis_telecharger_une_image(self):
        remi = self.jeton("remi")
        png = donnees_demo.png(40, 30, (200, 10, 10))
        r = self.http.post(f"{API}/tickets/1/images", files={"fichier": ("photo.png", png, "image/png")}, headers=remi)
        self.assertEqual(r.status_code, 201, r.text)
        image = r.json()
        self.assertEqual((image["largeur"], image["hauteur"]), (40, 30))
        self.assertEqual(r.headers["Location"], image["url"])
        telecharge = self.http.get(image["url"], headers=remi)
        self.assertEqual((telecharge.status_code, telecharge.headers["content-type"]), (200, "image/png"))
        self.assertEqual(telecharge.content, png)

    def test_image_refusee(self):
        remi = self.jeton("remi")
        exe = {"fichier": ("virus.exe", b"MZ\x90\x00", "application/octet-stream")}
        self.refus(self.http.post(f"{API}/tickets/1/images", files=exe, headers=remi), 422, "INVALIDE")
        faux = {"fichier": ("faux.png", b"pas une image", "image/png")}
        self.refus(self.http.post(f"{API}/tickets/1/images", files=faux, headers=remi), 422, "INVALIDE")

    def test_image_d_un_ticket_invisible_ou_inexistante(self):
        url = f"{API}/tickets/1/images/capture.png"
        self.assertEqual(self.http.get(url, headers=self.jeton("damien")).status_code, 200)
        self.refus(self.http.get(url, headers=self.jeton("rita")), 404, "INTROUVABLE")  # ticket de Remi
        self.refus(self.http.get(f"{API}/tickets/1/images/trace.txt", headers=self.jeton("remi")), 404, "INTROUVABLE")
        r = self.http.get(f"{API}/tickets/1/images/..%2F..%2Fdonnees_demo.py", headers=self.jeton("remi"))
        self.assertEqual(r.status_code, 404)
        self.refus(self.http.get(url), 401, "NON_CONNECTE")


class TestCommentairesEtArchives(Base):

    def test_commentaires(self):
        r = self.http.post(f"{API}/tickets/1/commentaires", json={"texte": "Je regarde"}, headers=self.jeton("diane"))
        self.assertEqual((r.status_code, r.json()["auteur"], r.json()["numero"]), (201, "Diane", 2))
        liste = self.http.get(f"{API}/tickets/1/commentaires", headers=self.jeton("remi")).json()
        self.assertEqual([c["texte"] for c in liste], ["Arrive à chaque redémarrage.", "Je regarde"])

    def test_archives(self):
        self.refus(self.http.post(f"{API}/archives", json={"numero": 2}, headers=self.jeton("rita")), 403, "INTERDIT")
        alice = self.jeton("alice")
        self.refus(self.http.post(f"{API}/archives", json={"numero": 2}, headers=alice), 409, "CONFLIT")  # OUVERT
        self.http.post(f"{API}/tickets/2/transitions", json={"action": "fermer", "motif": "doublon"}, headers=alice)
        r = self.http.post(f"{API}/archives", json={"numero": 2}, headers=alice)
        self.assertEqual((r.status_code, r.json()["archive"]), (201, True))
        self.assertEqual([t["numero"] for t in self.http.get(f"{API}/archives", headers=alice).json()], [2])
        actifs = self.http.get(f"{API}/tickets", params={"filtre": "tous"}, headers=alice).json()
        self.assertEqual([t["numero"] for t in actifs], [1])


class TestService(Base):

    def test_secret_trop_court(self):
        with self.assertRaises(ValueError):
            Jetons("court")

    def test_erreurs_du_cadriciel_ont_la_meme_forme(self):
        self.refus(self.http.get(f"{API}/inexistant"), 404, "INTROUVABLE")
        self.refus(self.http.delete(f"{API}/tickets"), 405, "INVALIDE")
        self.refus(self.http.post(f"{API}/sessions", content=b"pas du json",
                                  headers={"Content-Type": "application/json"}), 422, "INVALIDE")

    def test_page_web_servie_avec_l_api(self):
        from gestion_tickets.acteurs import UserRegistry
        from gestion_tickets.ticket import TicketRegistry
        users = UserRegistry("Admin", "admin@uqac.ca", "admin-web-2026")
        http = TestClient(creer_api(users, TicketRegistry(users), tempfile.mkdtemp(), secret=SECRET, web=True))
        page = http.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Gestionnaire de tickets", page.text)
        self.assertIn("Content-Security-Policy", page.text)
        self.assertEqual(http.get("/app.js").status_code, 200)
        self.assertEqual(http.get(f"{API}/sante").status_code, 200)  # l'API passe avant la page web
        self.refus(http.get(f"{API}/inexistant"), 404, "INTROUVABLE")

    def test_aucun_innerhtml_dans_la_page_web(self):
        """Les donnees recues ne deviennent jamais du HTML : pas d'injection de script possible."""
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "web", "app.js")
        with open(chemin, encoding="utf-8") as f:
            source = f.read()
        for interdit in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertNotIn(interdit, source)

    def test_racine_sans_page_web(self):
        r = self.http.get("/", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (307, "/docs"))

    def test_definition_openapi(self):
        chemins = set(self.http.get("/openapi.json").json()["paths"])
        attendus = {"/sessions", "/moi", "/comptes", "/comptes/{numero}", "/comptes/{numero}/roles",
                    "/comptes/{numero}/roles/{role}", "/tickets", "/tickets/{numero}", "/tickets/{numero}/contenus",
                    "/tickets/{numero}/textes", "/tickets/{numero}/images", "/tickets/{numero}/images/{nom}",
                    "/tickets/{numero}/commentaires", "/tickets/{numero}/transitions", "/archives", "/sante"}
        self.assertEqual(chemins, {API + c for c in attendus})

    def test_requetes_simultanees_gardent_leur_motif(self):
        """Le verrou du noyau. Deux refus differents en parallele ; chaque action est ralentie apres
        avoir ecrit son motif, pour que l'autre fil ecrive le sien dans le journal partage entre-temps.
        Sans le verrou, une requete recoit le motif de l'autre (essaye : le test echoue)."""
        diane, damien = self.jeton("diane"), self.jeton("damien")
        lent = {}
        for nom in ("validate", "reopen"):
            original = getattr(Ticket, nom)

            def ralenti(*args, _original=original, **kwargs):
                reponse = _original(*args, **kwargs)
                time.sleep(0.005)
                return reponse
            lent[nom] = mock.patch.object(Ticket, nom, ralenti)
        attendus = {"valider": None, "rouvrir": None}
        for action, jeton in (("valider", diane), ("rouvrir", damien)):
            attendus[action] = self.http.post(f"{API}/tickets/1/transitions", json={"action": action, "motif": "x"},
                                              headers=jeton).json()["motif"]
        self.assertNotEqual(attendus["valider"], attendus["rouvrir"])

        def demander(i):
            action, jeton = ("valider", diane) if i % 2 else ("rouvrir", damien)
            r = self.http.post(f"{API}/tickets/1/transitions", json={"action": action, "motif": "x"}, headers=jeton)
            return action, r.json()["motif"]

        with lent["validate"], lent["reopen"], ThreadPoolExecutor(8) as pool:
            reponses = list(pool.map(demander, range(40)))
        for action, motif in reponses:
            self.assertEqual(motif, attendus[action])

if __name__ == "__main__":
    unittest.main()
