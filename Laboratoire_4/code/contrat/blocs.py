"""Blocs d'affichage d'un ticket, dans l'ordre : le ticket, sa description, ses commentaires.

Ce sont des copies immuables. Un BlocImage designe un fichier lisible sur la machine
qui affiche : le dossier de televersement en local, le cache du client a travers l'API.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class BlocTicket:
    numero: int
    titre: str
    statut: str
    priorite: str
    auteur: str
    assigne: Optional[str]
    cree_le: datetime
    modifie_le: datetime
    archive_le: Optional[datetime]


@dataclass(frozen=True)
class BlocTexte:
    nom: str
    texte: str


@dataclass(frozen=True)
class BlocImage:
    nom: str
    chemin: str
    largeur: Optional[int]
    hauteur: Optional[int]

    @property
    def lisible(self) -> bool:
        return self.largeur is not None

    @property
    def texte_de_remplacement(self) -> str:
        """Nom accessible de l'image (critere WCAG 1.1.1)."""
        if not self.lisible:
            return f"Image {self.nom}, illisible"
        return f"Image {self.nom}, {self.largeur} × {self.hauteur} pixels"


@dataclass(frozen=True)
class BlocVideo:
    nom: str


@dataclass(frozen=True)
class BlocCommentaire:
    numero: int
    auteur: str
    publie_le: datetime
    texte: str
