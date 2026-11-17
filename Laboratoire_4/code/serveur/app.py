"""Assemblage du serveur : modele -> noyau (verrou) -> controleurs FastAPI -> page web.

Lancement local, depuis le dossier code :
    uvicorn serveur.app:creer_api_demo --factory --reload
Definition OpenAPI : /openapi.json ; documentation interactive : /docs.
"""
import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import reponses, routes_comptes, routes_tickets
from .noyau import Noyau
from .schemas import PREFIXE, Sante
from .securite import Jetons

VERSION = "4.0.0"
WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")

DESCRIPTION = """API REST du gestionnaire de tickets (6GEI311, laboratoire 4).

Toutes les regles restent celles du modele du labo 2 : le serveur ne fait que les exposer.
Pour essayer : `POST /api/v1/sessions` avec un compte de demonstration (alice@uqac.ca / alice-2026),
puis bouton **Authorize** avec le jeton recu.

Erreurs : toujours `{motif, details, cause}`. 401 jeton absent ou invalide ; 403 permission absente des
roles ; 404 ressource inexistante ou invisible ; 409 l'etat du ticket ne le permet pas ; 422 argument refuse.
"""

ETIQUETTES = [
    {"name": "sessions", "description": "Connexion (jeton d'acces) et profil du compte connecte"},
    {"name": "comptes", "description": "Inscription, liste, roles, activation"},
    {"name": "tickets", "description": "Creation, liste, consultation, titre et priorite"},
    {"name": "description", "description": "Textes et images de la description d'un ticket"},
    {"name": "commentaires", "description": "Commentaires d'un ticket"},
    {"name": "cycle de vie", "description": "Transitions du patron State"},
    {"name": "archives", "description": "Tickets archives"},
    {"name": "service", "description": "Etat du serveur"},
]


def creer_api(users, tickets, dossier_televersement: str, secret: str = None, web: bool = True) -> FastAPI:
    """Assemble l'API sur des registres deja construits (injection des dependances)."""
    app = FastAPI(title="Gestionnaire de tickets : API REST", version=VERSION, description=DESCRIPTION,
                  openapi_tags=ETIQUETTES)
    app.state.noyau = Noyau(users, tickets, dossier_televersement)
    app.state.jetons = Jetons(secret)
    reponses.installer(app)

    @app.get(f"{PREFIXE}/sante", response_model=Sante, tags=["service"],
             summary="Le serveur repond (utilise par le client pour le reveiller)")
    def sante():
        return Sante(version=VERSION)

    app.include_router(routes_comptes.routeur, prefix=PREFIXE)
    app.include_router(routes_tickets.routeur, prefix=PREFIXE)
    if web and os.path.isdir(WEB):
        app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    else:  # sans page web, la racine mene a la documentation interactive
        @app.get("/", include_in_schema=False)
        def racine():
            return RedirectResponse("/docs")
    return app


def creer_api_demo() -> FastAPI:
    """Serveur de demonstration : cinq comptes et deux tickets, en memoire.

    Variables d'environnement : TICKETS_SECRET (signature des jetons), TICKETS_PBKDF2_ITERATIONS
    (cout du hachage, a baisser sur une machine tres lente), TICKETS_UPLOAD_DIR (televersements).
    """
    from donnees_demo import TELEVERSEMENTS, creer_systeme
    from gestion_tickets.acteurs import UserRegistry

    iterations = os.environ.get("TICKETS_PBKDF2_ITERATIONS")
    if iterations:
        UserRegistry.PBKDF2_ITERATIONS = int(iterations)
    users, tickets = creer_systeme()
    return creer_api(users, tickets, TELEVERSEMENTS, os.environ.get("TICKETS_SECRET"))
