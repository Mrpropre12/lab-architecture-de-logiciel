"""Controleur des ressources Ticket, Contenu, Image, Commentaire, Transition et Archive.

Chaque route : compte du jeton -> services ouverts sur ce compte (sous le verrou) ->
un appel de service -> representation JSON, ou Refus traduit par reponses.py.
"""
import mimetypes
import os
import tempfile
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import FileResponse

import contrat
from contrat import ASSIGNES_A_MOI, MES_TICKETS, TOUS, Cause, Priority, Status
from gestion_tickets.acteurs import User

from . import schemas as s
from .dependances import compte_connecte, noyau
from .noyau import Noyau
from .reponses import exiger, refuser

routeur = APIRouter()
_ERREURS = {code: {"model": s.Erreur} for code in (401, 403, 404, 409, 422)}
LIMITE_IMAGE = 10 * 1024 * 1024  # meme limite que la fabrique du labo 2


def _detail(tickets, numero: int) -> contrat.DetailTicket:
    return exiger(tickets.detail(numero))


def _derniers(d: contrat.DetailTicket, type_bloc):
    blocs = [b for b in d.blocs if isinstance(b, type_bloc)]
    return blocs[-1]


# ------------------------------------------------ tickets
@routeur.get("/tickets", response_model=List[s.LigneJSON], tags=["tickets"], responses=_ERREURS,
             summary="Lister les tickets actifs visibles, filtres par le modele")
def lister(filtre: Literal["mes_tickets", "tous", "assignes_a_moi"] = MES_TICKETS,
           statut: Optional[Status] = None, priorite: Optional[Priority] = None,
           compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    assert filtre in (MES_TICKETS, TOUS, ASSIGNES_A_MOI)
    with n.services(compte) as (_, _c, tickets):
        return [s.ligne(l) for l in exiger(tickets.lister(filtre, statut, priorite))]


@routeur.post("/tickets", status_code=201, response_model=s.TicketCree, tags=["tickets"], responses=_ERREURS,
              summary="Creer un ticket (CREATE), avec un premier texte facultatif")
def creer(corps: s.NouveauTicket, response: Response, compte: User = Depends(compte_connecte),
          n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, _c, tickets):
        r = tickets.creer(corps.titre, corps.priorite, corps.texte)
        numero = exiger(r)
    response.headers["Location"] = f"{s.PREFIXE}/tickets/{numero}"
    return s.TicketCree(numero=numero, details=list(r.details))


@routeur.get("/tickets/{numero}", response_model=s.DetailJSON, tags=["tickets"], responses=_ERREURS,
             summary="Consulter un ticket : blocs a afficher et actions permises maintenant")
def consulter(numero: int, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, _c, tickets):
        return s.detail(_detail(tickets, numero))


@routeur.patch("/tickets/{numero}", response_model=s.DetailJSON, tags=["tickets"], responses=_ERREURS,
               summary="Modifier le titre (EDIT) et/ou la priorite (SET_PRIORITY)")
def modifier(numero: int, corps: s.ModifTicket, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    if corps.titre is None and corps.priorite is None:
        refuser("rien a modifier : donnez titre et/ou priorite")
    with n.services(compte) as (_, _c, tickets):
        if corps.titre is not None:
            exiger(tickets.modifier_titre(numero, corps.titre))
        if corps.priorite is not None:
            exiger(tickets.changer_priorite(numero, corps.priorite))
        return s.detail(_detail(tickets, numero))


# ------------------------------------------------ description : textes et images
@routeur.get("/tickets/{numero}/contenus", response_model=List[s.BlocContenuJSON], tags=["description"],
             responses=_ERREURS, summary="Lister la description : textes, images et videos, dans l'ordre")
def contenus(numero: int, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, _c, tickets):
        d = _detail(tickets, numero)
    types = (contrat.BlocTexte, contrat.BlocImage, contrat.BlocVideo)
    return [s.bloc(numero, b) for b in d.blocs if isinstance(b, types)]


@routeur.post("/tickets/{numero}/textes", status_code=201, response_model=s.BlocTexteJSON, tags=["description"],
              responses=_ERREURS, summary="Ajouter un texte a la description (ATTACH, auteur)")
def ajouter_texte(numero: int, corps: s.Texte, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, _c, tickets):
        exiger(tickets.ajouter_texte(numero, corps.texte))
        return s.bloc(numero, _derniers(_detail(tickets, numero), contrat.BlocTexte))


@routeur.post("/tickets/{numero}/images", status_code=201, response_model=s.BlocImageJSON, tags=["description"],
              responses=_ERREURS, summary="Joindre une image .png, .jpg ou .gif (ATTACH, auteur)")
def joindre_image(numero: int, response: Response, fichier: UploadFile = File(...),
                  compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    donnees = fichier.file.read(LIMITE_IMAGE + 1)
    if len(donnees) > LIMITE_IMAGE:
        refuser("image de plus de 10 Mo")
    extension = os.path.splitext(fichier.filename or "")[1].lower()
    with tempfile.TemporaryDirectory() as dossier:
        chemin = os.path.join(dossier, "televersement" + extension)
        with open(chemin, "wb") as f:
            f.write(donnees)
        with n.services(compte) as (_, _c, tickets):
            exiger(tickets.joindre_image(numero, chemin))  # copie, puis verification par la fabrique
            image = s.bloc(numero, _derniers(_detail(tickets, numero), contrat.BlocImage))
    response.headers["Location"] = image.url
    return image


@routeur.get("/tickets/{numero}/images/{nom}", tags=["description"], response_class=FileResponse,
             responses={200: {"content": {"image/png": {}, "image/jpeg": {}, "image/gif": {}}}, **_ERREURS},
             summary="Telecharger une image de la description (seulement si le ticket est visible)")
def telecharger_image(numero: int, nom: str, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, _c, tickets):
        d = _detail(tickets, numero)
    # Seuls les noms des blocs du modele sont servis : aucun chemin construit depuis l'URL.
    image = next((b for b in d.blocs if isinstance(b, contrat.BlocImage) and b.nom == nom), None)
    if image is None or not os.path.isfile(image.chemin):
        refuser(f"image {nom} absente du ticket {numero}", Cause.INTROUVABLE)
    type_mime = mimetypes.guess_type(image.nom)[0] or "application/octet-stream"
    return FileResponse(image.chemin, media_type=type_mime, headers={"Cache-Control": "private, max-age=3600"})


# ------------------------------------------------ commentaires
@routeur.get("/tickets/{numero}/commentaires", response_model=List[s.BlocCommentaireJSON], tags=["commentaires"],
             responses=_ERREURS, summary="Lister les commentaires d'un ticket")
def commentaires(numero: int, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, _c, tickets):
        d = _detail(tickets, numero)
    return [s.bloc(numero, b) for b in d.blocs if isinstance(b, contrat.BlocCommentaire)]


@routeur.post("/tickets/{numero}/commentaires", status_code=201, response_model=s.BlocCommentaireJSON,
              tags=["commentaires"], responses=_ERREURS, summary="Commenter un ticket (COMMENT)")
def commenter(numero: int, corps: s.Texte, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, _c, tickets):
        return s.bloc(numero, exiger(tickets.commenter(numero, corps.texte)))


# ------------------------------------------------ cycle de vie
@routeur.post("/tickets/{numero}/transitions", status_code=201, response_model=s.TransitionJSON,
              tags=["cycle de vie"], responses=_ERREURS,
              summary="Demander une transition : assigner, soumettre, valider, rejeter, fermer ou rouvrir")
def transition(numero: int, corps: s.Transition, compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    """Le modele accepte ou refuse selon l'etat du ticket et les roles du compte (patron State)."""
    with n.services(compte) as (_, _c, t):
        if corps.action == "assigner":
            if corps.assigne is None:
                refuser("assigner exige le numero du compte assigne (champ assigne)")
            r = t.assigner(numero, corps.assigne)
        elif corps.action in ("soumettre", "valider"):
            r = getattr(t, corps.action)(numero)
        else:
            r = getattr(t, corps.action)(numero, corps.motif or "")
        exiger(r)
        tete = _detail(t, numero).blocs[0]
    return s.TransitionJSON(action=corps.action, statut=Status(tete.statut))


# ------------------------------------------------ archives
@routeur.get("/archives", response_model=List[s.LigneJSON], tags=["archives"], responses=_ERREURS,
             summary="Lister les tickets archives visibles")
def archives(compte: User = Depends(compte_connecte), n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, _c, tickets):
        return [s.ligne(l) for l in exiger(tickets.archives())]


@routeur.post("/archives", status_code=201, response_model=s.LigneJSON, tags=["archives"], responses=_ERREURS,
              summary="Archiver un ticket (ARCHIVE)")
def archiver(corps: s.Archivage, response: Response, compte: User = Depends(compte_connecte),
             n: Noyau = Depends(noyau)):
    with n.services(compte) as (_, _c, tickets):
        exiger(tickets.archiver(corps.numero))
        ligne = next(l for l in exiger(tickets.archives()) if l.numero == corps.numero)
    response.headers["Location"] = f"{s.PREFIXE}/tickets/{corps.numero}"
    return s.ligne(ligne)
