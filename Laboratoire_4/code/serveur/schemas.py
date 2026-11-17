"""Representations JSON des ressources (schemas Pydantic, publies dans la definition OpenAPI).

Les sorties sont construites a partir des types du contrat ; aucune n'expose un objet
du modele ni un chemin du disque du serveur : une image est designee par son URL.
"""
from datetime import datetime
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field

import contrat
from contrat import Permission, Priority, Status

PREFIXE = "/api/v1"


# ------------------------------------------------ erreurs et service
class Erreur(BaseModel):
    motif: str = Field(examples=["valider exige l'etat VALIDATION"])
    details: List[str] = []
    cause: str = Field(examples=["CONFLIT"])


class Sante(BaseModel):
    etat: str = "ok"
    version: str


# ------------------------------------------------ sessions et comptes
class Connexion(BaseModel):
    courriel: str = Field(examples=["alice@uqac.ca"])
    mot_de_passe: str = Field(examples=["alice-2026"])


class ProfilJSON(BaseModel):
    numero: int
    nom: str
    roles: List[str]
    permissions: List[Permission]


class SessionJSON(BaseModel):
    jeton: str
    type: str = "bearer"
    expire_le: datetime
    profil: ProfilJSON


class Inscription(BaseModel):
    nom: str
    courriel: str
    mot_de_passe: str
    confirmation: str


class Inscrit(BaseModel):
    """Nom du compte concerne, et remarques du service (ex. : le compte s'est desactive lui-meme)."""
    nom: str
    details: List[str] = []


class CompteJSON(BaseModel):
    numero: int
    nom: str
    roles: List[str]
    actif: bool


class ModifCompte(BaseModel):
    actif: bool


class NouveauRole(BaseModel):
    """Le nom est verifie par le service (motif « role inconnu ») : un seul endroit decide."""
    role: str = Field(description="Rapporteur, Developpeur ou Administrateur", examples=["Developpeur"])


# ------------------------------------------------ tickets
class LigneJSON(BaseModel):
    numero: int
    titre: str
    statut: Status
    priorite: Priority
    auteur: str
    assigne: Optional[str]
    modifie_le: datetime
    archive: bool


class NouveauTicket(BaseModel):
    titre: str = Field(examples=["Le bouton Enregistrer ne repond plus"])
    priorite: Priority = Priority.NORMALE
    texte: str = ""


class TicketCree(BaseModel):
    numero: int
    details: List[str] = []


class ModifTicket(BaseModel):
    titre: Optional[str] = None
    priorite: Optional[Priority] = None


class BlocTicketJSON(BaseModel):
    type: Literal["ticket"] = "ticket"
    numero: int
    titre: str
    statut: Status
    priorite: Priority
    auteur: str
    assigne: Optional[str]
    cree_le: datetime
    modifie_le: datetime
    archive_le: Optional[datetime]


class BlocTexteJSON(BaseModel):
    type: Literal["texte"] = "texte"
    nom: str
    texte: str


class BlocImageJSON(BaseModel):
    type: Literal["image"] = "image"
    nom: str
    url: str
    largeur: Optional[int]
    hauteur: Optional[int]


class BlocVideoJSON(BaseModel):
    type: Literal["video"] = "video"
    nom: str


class BlocCommentaireJSON(BaseModel):
    type: Literal["commentaire"] = "commentaire"
    numero: int
    auteur: str
    publie_le: datetime
    texte: str


BlocContenuJSON = Annotated[Union[BlocTexteJSON, BlocImageJSON, BlocVideoJSON], Field(discriminator="type")]
BlocJSON = Annotated[Union[BlocTicketJSON, BlocTexteJSON, BlocImageJSON, BlocVideoJSON, BlocCommentaireJSON],
                     Field(discriminator="type")]


class DetailJSON(BaseModel):
    numero: int
    blocs: List[BlocJSON]
    actions: List[Permission]
    texte: str


class Texte(BaseModel):
    texte: str


Action = Literal["assigner", "soumettre", "valider", "rejeter", "fermer", "rouvrir"]


class Transition(BaseModel):
    action: Action
    motif: Optional[str] = Field(None, description="exige pour rejeter, fermer et rouvrir")
    assigne: Optional[int] = Field(None, description="numero du compte, exige pour assigner")


class TransitionJSON(BaseModel):
    action: Action
    statut: Status


class Archivage(BaseModel):
    numero: int


# ------------------------------------------------ contrat -> JSON
def _date(d: Optional[datetime]) -> Optional[datetime]:
    """Le modele date a l'heure locale du serveur, sans fuseau. Render tourne en UTC :
    on joint le fuseau du serveur, et le client convertit vers son heure locale."""
    return d.astimezone() if d is not None else None


def profil(p: contrat.Profil) -> ProfilJSON:
    return ProfilJSON(numero=p.numero, nom=p.nom, roles=list(p.roles), permissions=list(p.permissions))


def compte(c: contrat.CompteVue) -> CompteJSON:
    return CompteJSON(numero=c.numero, nom=c.nom, roles=list(c.roles), actif=c.actif)


def ligne(l: contrat.LigneTicket) -> LigneJSON:
    return LigneJSON(numero=l.numero, titre=l.titre, statut=l.statut, priorite=l.priorite, auteur=l.auteur,
                     assigne=l.assigne, modifie_le=_date(l.modifie_le), archive=l.archive)


def url_image(numero: int, nom: str) -> str:
    return f"{PREFIXE}/tickets/{numero}/images/{nom}"


def bloc(numero: int, b):
    if isinstance(b, contrat.BlocTicket):
        return BlocTicketJSON(numero=b.numero, titre=b.titre, statut=Status(b.statut), priorite=Priority(b.priorite),
                              auteur=b.auteur, assigne=b.assigne, cree_le=_date(b.cree_le), modifie_le=_date(b.modifie_le),
                              archive_le=_date(b.archive_le))
    if isinstance(b, contrat.BlocTexte):
        return BlocTexteJSON(nom=b.nom, texte=b.texte)
    if isinstance(b, contrat.BlocImage):
        return BlocImageJSON(nom=b.nom, url=url_image(numero, b.nom), largeur=b.largeur, hauteur=b.hauteur)
    if isinstance(b, contrat.BlocVideo):
        return BlocVideoJSON(nom=b.nom)
    return BlocCommentaireJSON(numero=b.numero, auteur=b.auteur, publie_le=_date(b.publie_le), texte=b.texte)


def detail(d: contrat.DetailTicket) -> DetailJSON:
    ordre = list(Permission)
    return DetailJSON(numero=d.numero, blocs=[bloc(d.numero, b) for b in d.blocs],
                      actions=sorted(d.actions, key=ordre.index), texte=d.texte)
