"""Pont entre le modele du labo 2 et le contrat partage (labo 4).

Le modele garde ses propres enumerations et ses propres blocs ; le contrat a les siens,
de meme nom et de meme valeur. La traduction se fait ici, et seulement ici : c'est la
gestion des differences syntaxiques entre composants vue en cours (S6).
"""
from dataclasses import fields

import contrat
from gestion_tickets import consultation as _consultation
from gestion_tickets.acteurs import Permission as _Permission
from gestion_tickets.ticket import Comment, Priority as _Priority, Status as _Status

_BLOCS = {
    _consultation.BlocTicket: contrat.BlocTicket,
    _consultation.BlocTexte: contrat.BlocTexte,
    _consultation.BlocImage: contrat.BlocImage,
    _consultation.BlocVideo: contrat.BlocVideo,
    _consultation.BlocCommentaire: contrat.BlocCommentaire,
}


# ------------------------------------------------ modele -> contrat
def statut(s: _Status) -> contrat.Status:
    return contrat.Status(s.value)


def priorite(p: _Priority) -> contrat.Priority:
    return contrat.Priority(p.value)


def permission(p: _Permission) -> contrat.Permission:
    return contrat.Permission(p.value)


def permissions(ps) -> frozenset:
    return frozenset(permission(p) for p in ps)


def bloc(b):
    """Copie champ par champ d'un bloc du DescriptionVisitor vers le bloc du contrat."""
    cible = _BLOCS[type(b)]
    return cible(**{f.name: getattr(b, f.name) for f in fields(b)})


def commentaire(c: Comment) -> contrat.BlocCommentaire:
    return contrat.BlocCommentaire(c.comment_id, c.get_author().name, c.posted_at, c.text)


# ------------------------------------------------ contrat -> modele (par la valeur)
def vers_priorite(p) -> _Priority:
    return _Priority(p.value)


def vers_statut(s) -> _Status:
    return _Status(s.value)


def vers_permission(p) -> _Permission:
    return _Permission(p.value)
