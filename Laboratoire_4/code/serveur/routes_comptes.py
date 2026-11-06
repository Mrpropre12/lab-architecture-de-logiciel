"""Controleur des ressources Session, Profil, Compte et Role d'un compte."""
from typing import List

from fastapi import APIRouter, Depends, Response

from gestion_tickets.acteurs import User

from . import schemas as s
from .dependances import compte_connecte, jetons, noyau
from .noyau import Noyau
from .reponses import exiger
from .securite import Jetons

routeur = APIRouter()
_PUBLIC = {401: {"model": s.Erreur}, 422: {"model": s.Erreur}}
_PROTEGE = {401: {"model": s.Erreur}, 403: {"model": s.Erreur}, 404: {"model": s.Erreur},
            409: {"model": s.Erreur}, 422: {"model": s.Erreur}}


# ------------------------------------------------ sessions
@routeur.post("/sessions", status_code=201, response_model=s.SessionJSON, tags=["sessions"], responses=_PUBLIC,
              summary="Se connecter : echange courriel et mot de passe contre un jeton d'acces")
def ouvrir_session(corps: s.Connexion, n: Noyau = Depends(noyau), j: Jetons = Depends(jetons)):
    r, compte = n.connecter(corps.courriel, corps.mot_de_passe)
    profil = exiger(r)
    jeton, expire = j.emettre(compte.user_id)
    return s.SessionJSON(jeton=jeton, expire_le=expire, profil=s.profil(profil))


@routeur.get("/moi", response_model=s.ProfilJSON, tags=["sessions"], responses=_PROTEGE,
             summary="Profil du compte connecte : roles et permissions")
def moi(compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, comptes, _t):
        return s.profil(exiger(comptes.profil()))


# ------------------------------------------------ comptes
@routeur.post("/comptes", status_code=201, response_model=s.Inscrit, tags=["comptes"], responses=_PUBLIC,
              summary="S'inscrire (role Rapporteur)")
def inscrire(corps: s.Inscription, n: Noyau = Depends(noyau)):
    with n.services() as (_, comptes, _t):
        return s.Inscrit(nom=exiger(comptes.inscrire(corps.nom, corps.courriel, corps.mot_de_passe, corps.confirmation)))


@routeur.get("/comptes", response_model=List[s.CompteJSON], tags=["comptes"], responses=_PROTEGE,
             summary="Lister les comptes (MANAGE_USERS), ou seulement ceux qu'on peut assigner")
def lister_comptes(assignables: bool = False, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, comptes, tickets):
        r = tickets.assignables() if assignables else comptes.lister()
        return [s.compte(c) for c in exiger(r)]


@routeur.patch("/comptes/{numero}", response_model=s.Inscrit, tags=["comptes"], responses=_PROTEGE,
               summary="Activer ou desactiver un compte (MANAGE_USERS)")
def modifier_compte(numero: int, corps: s.ModifCompte, compte: User = Depends(compte_connecte),
                    n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, comptes, _t):
        r = comptes.reactiver(numero) if corps.actif else comptes.desactiver(numero)
        return s.Inscrit(nom=exiger(r))


@routeur.post("/comptes/{numero}/roles", status_code=201, response_model=s.Inscrit, tags=["comptes"],
              responses=_PROTEGE, summary="Attribuer un role a un compte (MANAGE_USERS)")
def attribuer_role(numero: int, corps: s.NouveauRole, compte: User = Depends(compte_connecte),
                   n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, comptes, _t):
        return s.Inscrit(nom=exiger(comptes.attribuer_role(numero, corps.role)))


@routeur.delete("/comptes/{numero}/roles/{role}", status_code=204, tags=["comptes"], responses=_PROTEGE,
                summary="Retirer un role a un compte (MANAGE_USERS)")
def retirer_role(numero: int, role: str, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, comptes, _t):
        exiger(comptes.retirer_role(numero, role))
    return Response(status_code=204)

