"""Donnees que l'interface affiche. Ce sont des copies immuables : l'interface ne
manipule jamais un objet du modele, seulement des numeros et ces vues."""
from dataclasses import dataclass
from datetime import datetime
from typing import FrozenSet, Optional, Tuple

from gestion_tickets.acteurs import Permission
from gestion_tickets.ticket import Priority, Status


@dataclass(frozen=True)
class LigneTicket:
    numero: int
    titre: str
    statut: Status
    priorite: Priority
    auteur: str
    assigne: Optional[str]
    modifie_le: datetime
    archive: bool


@dataclass(frozen=True)
class DetailTicket:
    """Blocs du DescriptionVisitor et actions permises a l'acteur en ce moment."""
    numero: int
    blocs: Tuple[object, ...]
    actions: FrozenSet[Permission]
    texte: str  # version texte de toute la description (alternative textuelle)


@dataclass(frozen=True)
class CompteVue:
    numero: int
    nom: str
    roles: Tuple[str, ...]
    actif: bool


@dataclass(frozen=True)
class Profil:
    numero: int
    nom: str
    roles: Tuple[str, ...]
    permissions: Tuple[Permission, ...]
