"""Consultation pour une interface graphique : la description d'un ticket en blocs.

Ce visiteur ne depend d'aucune bibliotheque graphique. Il transforme le ticket en
une suite de blocs de donnees (en-tete, texte, image, video, commentaire) qu'une
interface, Qt ou autre, n'a plus qu'a dessiner. result() respecte le contrat de
ViewVisitor : il renvoie une version texte, qui sert aussi d'alternative textuelle.

Comme pour ScreenRenderVisitor, l'ajout de ce visiteur ne change ni Ticket ni les
contenus : c'est l'interet du patron Visiteur.
"""
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from ..ticket import ViewVisitor


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


def _date(d: Optional[datetime]) -> str:
    return d.strftime("%Y-%m-%d %H:%M") if d else ""


class DescriptionVisitor(ViewVisitor):
    """Construit les blocs ; un nouveau parcours recommence a zero."""

    def __init__(self) -> None:
        self.__blocks = []

    def blocks(self) -> Tuple[object, ...]:
        """Blocs dans l'ordre du parcours : le ticket, sa description, puis ses commentaires."""
        return tuple(self.__blocks)

    def visit_ticket(self, t) -> None:
        assigne = t.get_assignee()
        self.__blocks = [BlocTicket(t.ticket_id, t.title, t.get_status().value, t.priority.value,
                                    t.get_author().name, assigne.name if assigne else None,
                                    t.creation_date, t.update_date, t.archive_date)]

    def visit_text(self, c) -> None:
        self.__blocks.append(BlocTexte(os.path.basename(c.path), c.text or ""))

    def visit_image(self, c) -> None:
        """Premier affichage : l'image est chargee ici (dimensions lues, puis gardees en cache)."""
        lisible = c.load()
        self.__blocks.append(BlocImage(os.path.basename(c.path), c.path,
                                       c.width if lisible else None, c.height if lisible else None))

    def visit_video(self, c) -> None:
        self.__blocks.append(BlocVideo(os.path.basename(c.path)))

    def visit_comment(self, c) -> None:
        self.__blocks.append(BlocCommentaire(c.comment_id, c.get_author().name, c.posted_at, c.text))

    def result(self) -> str:
        """Version texte de la description, dans l'ordre des blocs."""
        lignes = []
        for b in self.__blocks:
            if isinstance(b, BlocTicket):
                archive = f", archive le {_date(b.archive_le)}" if b.archive_le else ""
                lignes += [f"Ticket {b.numero} : {b.titre}",
                           f"Statut {b.statut}{archive}, priorite {b.priorite}",
                           f"Auteur {b.auteur}, assigne {b.assigne or 'aucun'}"]
            elif isinstance(b, BlocTexte):
                lignes += [f"Texte {b.nom} :", b.texte]
            elif isinstance(b, BlocImage):
                lignes.append(b.texte_de_remplacement)
            elif isinstance(b, BlocVideo):
                lignes.append(f"Video {b.nom}, non prise en charge dans cette version")
            else:
                lignes.append(f"Commentaire {b.numero} de {b.auteur}, {_date(b.publie_le)} : {b.texte}")
        return "\n".join(lignes)
