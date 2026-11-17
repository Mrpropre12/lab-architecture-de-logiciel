"""Cycle de vie du ticket (patron State).

Un etat n'autorise que les transitions qu'il redefinit : toutes les autres
sont refusees par defaut dans TicketState. Les transitions sont reservees au
paquetage (~) : seul Ticket les appelle, apres avoir verifie le droit global.

Chaque transition accepte apply=False : elle repond alors seulement a la
question « serait-ce permis ? », sans effet et sans motif au journal. C'est ce
qui permet a Ticket.allowed_actions de reutiliser exactement les memes regles.
"""
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..acteurs import User
    from .ticket import Ticket

_journal = logging.getLogger(__name__)


def _refus(motif: str, apply: bool = True) -> bool:
    if apply:
        _journal.info("refus : %s", motif)
    return False


class Status(Enum):
    OUVERT = "OUVERT"
    ASSIGNE = "ASSIGNE"
    VALIDATION = "VALIDATION"
    TERMINE = "TERMINE"
    FERME = "FERME"


class TicketState(ABC):
    """Etat abstrait : chaque transition est refusee tant qu'un etat ne la redefinit pas."""

    def _assign(self, t: "Ticket", actor: "User", assignee: "User", apply: bool = True) -> bool:
        return _refus(f"assigner est impossible en {self.name().value}", apply)

    def _submit(self, t: "Ticket", actor: "User", apply: bool = True) -> bool:
        return _refus(f"soumettre est impossible en {self.name().value}", apply)

    def _validate(self, t: "Ticket", actor: "User", apply: bool = True) -> bool:
        return _refus(f"valider est impossible en {self.name().value}", apply)

    def _reject(self, t: "Ticket", actor: "User", reason: str, apply: bool = True) -> bool:
        return _refus(f"rejeter est impossible en {self.name().value}", apply)

    def _close(self, t: "Ticket", actor: "User", reason: str, apply: bool = True) -> bool:
        return _refus(f"fermer est impossible en {self.name().value}", apply)

    def _reopen(self, t: "Ticket", actor: "User", reason: str, apply: bool = True) -> bool:
        return _refus(f"reouvrir est impossible en {self.name().value}", apply)

    def allows_edit(self) -> bool:
        """Vrai si le titre et la description sont encore modifiables."""
        return True

    @abstractmethod
    def name(self) -> Status:
        """Statut correspondant a l'etat."""

    def _is_assignee(self, t: "Ticket", u: "User") -> bool:
        """Regle contextuelle : u est-il l'assigne de ce ticket ?"""
        return u is not None and t.get_assignee() is u

    def __repr__(self) -> str:
        return self.name().value


class OpenState(TicketState):

    def _assign(self, t, actor, assignee, apply=True) -> bool:
        if apply:
            t._set_assignee(assignee)
            t._set_state(AssignedState())
        return True

    def _close(self, t, actor, reason, apply=True) -> bool:
        if apply:
            t._set_state(ClosedState())
        return True

    def name(self) -> Status:
        return Status.OUVERT


class AssignedState(TicketState):

    def _assign(self, t, actor, assignee, apply=True) -> bool:
        """Reassignation, meme si l'assigne actuel est desactive."""
        if apply and t.get_assignee() is assignee:  # sans effet : on ne connait pas encore l'assigne
            return _refus("le ticket est deja assigne a cette personne")
        if apply:
            t._set_assignee(assignee)
        return True

    def _submit(self, t, actor, apply=True) -> bool:
        if not self._is_assignee(t, actor):
            return _refus("seul l'assigne soumet son travail a la validation", apply)
        if apply:
            t._set_state(ValidationState())
        return True

    def _close(self, t, actor, reason, apply=True) -> bool:
        if apply:
            t._set_state(ClosedState())
        return True

    def name(self) -> Status:
        return Status.ASSIGNE


class ValidationState(TicketState):

    def _validate(self, t, actor, apply=True) -> bool:
        if self._is_assignee(t, actor):
            return _refus("l'assigne ne valide pas son propre travail", apply)
        if apply:
            t._set_state(TerminatedState())
        return True

    def _reject(self, t, actor, reason, apply=True) -> bool:
        if self._is_assignee(t, actor):
            return _refus("l'assigne ne rejette pas son propre travail", apply)
        if apply:
            t._set_state(AssignedState())
        return True

    def _close(self, t, actor, reason, apply=True) -> bool:
        if apply:
            t._set_state(ClosedState())
        return True

    def name(self) -> Status:
        return Status.VALIDATION


class TerminatedState(TicketState):

    def _reopen(self, t, actor, reason, apply=True) -> bool:
        if apply:
            t._set_assignee(None)
            t._set_state(OpenState())
        return True

    def allows_edit(self) -> bool:
        return False

    def name(self) -> Status:
        return Status.TERMINE


class ClosedState(TicketState):

    def _reopen(self, t, actor, reason, apply=True) -> bool:
        if apply:
            t._set_assignee(None)
            t._set_state(OpenState())
        return True

    def allows_edit(self) -> bool:
        return False

    def name(self) -> Status:
        return Status.FERME
