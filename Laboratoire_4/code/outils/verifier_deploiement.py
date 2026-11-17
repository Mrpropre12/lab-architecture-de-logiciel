"""Verifie un serveur deploye avec le vrai client, et mesure les durees (labo 4).

Usage, depuis le dossier code :
    python outils/verifier_deploiement.py                 serveur par defaut (Render)
    python outils/verifier_deploiement.py http://127.0.0.1:8000

Comptes de demonstration seulement. Aucune donnee n'est modifiee : les seules actions
demandees sont des actions que le modele doit refuser.
"""
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))

from client import CacheImages, ClientComptes, ClientTickets, Transport  # noqa: E402
from contrat import BlocImage, Cause  # noqa: E402
from main import SERVEUR_PAR_DEFAUT  # noqa: E402

RESULTATS = []


def etape(nom, appel, attendu=lambda r: r.ok):
    debut = time.perf_counter()
    r = appel()
    duree = time.perf_counter() - debut
    ok = attendu(r)
    precision = "" if ok else f"  <- {getattr(r, 'motif', r)}"
    RESULTATS.append(ok)
    print(f"  {'OK ' if ok else 'ECHEC'}  {duree * 1000:7.0f} ms  {nom}{precision}")
    return r


def main(url) -> int:
    print(f"Serveur : {url}")
    t = Transport(url)
    comptes, tickets = ClientComptes(t), ClientTickets(t, CacheImages(t))
    try:
        etape("reveil (GET /sante, jusqu'a 90 s si le service dormait)", comptes.reveiller)
        etape("connexion refusee (mauvais mot de passe)", lambda: comptes.connecter("alice@uqac.ca", "pas-le-bon"),
              lambda r: r.cause == Cause.NON_CONNECTE)
        etape("connexion d'Alice (hachage PBKDF2 sur le serveur)",
              lambda: comptes.connecter("alice@uqac.ca", "alice-2026"))
        etape("profil", comptes.profil, lambda r: r.ok and r.valeur.nom == "Alice")
        etape("liste de tous les tickets", lambda: tickets.lister("tous"), lambda r: r.ok and len(r.valeur) >= 2)
        r = etape("detail du ticket 1 (image telechargee dans le cache)", lambda: tickets.detail(1))
        if r.ok:
            images = [b for b in r.valeur.blocs if isinstance(b, BlocImage)]
            etape("image lisible localement", lambda: images,
                  lambda imgs: bool(imgs) and all(i.lisible and os.path.isfile(i.chemin) for i in imgs))
        etape("valider un ticket ASSIGNE : refus 409 avec le motif du modele", lambda: tickets.valider(1),
              lambda r: r.cause == Cause.CONFLIT and "ASSIGNE" in (r.motif or ""))
        etape("liste des comptes (MANAGE_USERS)", comptes.lister, lambda r: r.ok and len(r.valeur) >= 5)
        comptes.deconnecter()
        etape("connexion de Remi (rapporteur)", lambda: comptes.connecter("remi@uqac.ca", "remi-2026"))
        etape("Remi : tous les tickets refuse (403)", lambda: tickets.lister("tous"),
              lambda r: r.cause == Cause.INTERDIT)
        etape("Remi : ticket de Rita invisible (404)", lambda: tickets.detail(2),
              lambda r: r.cause == Cause.INTROUVABLE)
        debut = time.perf_counter()
        for _ in range(10):
            tickets.lister()
        print(f"  info   {(time.perf_counter() - debut) * 100:7.0f} ms  par requete (moyenne de 10 listes)")
    finally:
        comptes.deconnecter()
        t.fin()
    echecs = RESULTATS.count(False)
    print(f"{len(RESULTATS) - echecs}/{len(RESULTATS)} verifications reussies")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else SERVEUR_PAR_DEFAUT))
