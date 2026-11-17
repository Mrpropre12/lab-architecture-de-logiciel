"""Dependances communes des controleurs : le noyau, et le compte qui porte le jeton."""
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from contrat import Cause
from gestion_tickets.acteurs import User

from .noyau import Noyau
from .reponses import refuser
from .securite import Jetons

_porteur = HTTPBearer(auto_error=False, description="Jeton recu de POST /api/v1/sessions")


def noyau(request: Request) -> Noyau:
    return request.app.state.noyau


def jetons(request: Request) -> Jetons:
    return request.app.state.jetons


def compte_connecte(request: Request, porteur: HTTPAuthorizationCredentials = Depends(_porteur)) -> User:
    """Compte du jeton, verifie a chaque requete (sans etat) ; 401 sinon."""
    if porteur is None:
        refuser("jeton d'acces manquant : connectez-vous avec POST /api/v1/sessions", Cause.NON_CONNECTE)
    numero = jetons(request).lire(porteur.credentials)
    if numero is None:
        refuser("jeton invalide ou expire : reconnectez-vous", Cause.NON_CONNECTE)
    compte = noyau(request).compte(numero)
    if compte is None:
        refuser("compte desactive, ou serveur redemarre depuis la connexion : reconnectez-vous", Cause.NON_CONNECTE)
    return compte
