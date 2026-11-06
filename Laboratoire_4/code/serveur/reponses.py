"""Traduction d'un Resultat refuse en reponse HTTP. Une seule table : cause -> code.

Le motif reste celui ecrit par le modele, comme dans le bandeau REFUSE du labo 3.
"""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from contrat import Cause, Resultat

CODES = {
    Cause.NON_CONNECTE: 401,
    Cause.INTERDIT: 403,
    Cause.INTROUVABLE: 404,
    Cause.CONFLIT: 409,
    Cause.INVALIDE: 422,
    Cause.INJOIGNABLE: 503,
}
_CAUSES = {code: cause for cause, code in CODES.items()}


class Refus(Exception):
    """Levee par un controleur quand un service refuse ; transformee en reponse JSON."""

    def __init__(self, resultat: Resultat) -> None:
        super().__init__(resultat.motif)
        self.resultat = resultat


def exiger(r: Resultat):
    """Valeur d'un Resultat accepte ; sinon Refus."""
    if not r.ok:
        raise Refus(r)
    return r.valeur


def refuser(motif: str, cause: Cause = Cause.INVALIDE):
    raise Refus(Resultat.echec(motif, cause=cause))


def _erreur(code: int, motif: str, details=(), cause: Cause = Cause.INVALIDE) -> JSONResponse:
    entetes = {"WWW-Authenticate": "Bearer"} if code == 401 else None
    return JSONResponse({"motif": motif, "details": list(details), "cause": cause.value}, code, headers=entetes)


def installer(app) -> None:
    """Toutes les erreurs ont la meme forme : {motif, details, cause}."""

    @app.exception_handler(Refus)
    def _refus(_: Request, e: Refus):
        r = e.resultat
        return _erreur(CODES[r.cause or Cause.INVALIDE], r.motif or "refuse", r.details, r.cause or Cause.INVALIDE)

    @app.exception_handler(RequestValidationError)
    def _validation(_: Request, e: RequestValidationError):
        details = [f"{'.'.join(str(x) for x in err['loc'] if x != 'body')} : {err['msg']}" for err in e.errors()]
        return _erreur(422, "requete invalide", details)

    @app.exception_handler(StarletteHTTPException)
    def _http(_: Request, e: StarletteHTTPException):
        motifs = {404: "ressource inexistante", 405: "methode non permise sur cette ressource"}
        motif = motifs.get(e.status_code, str(e.detail))
        return _erreur(e.status_code, motif, cause=_CAUSES.get(e.status_code, Cause.INVALIDE))
