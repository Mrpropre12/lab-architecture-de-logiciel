"""Le ticket, ses commentaires et sa priorite.

Chaque action suit le meme ordre de controle :
1. droit global : __authorize (permission du role, compte actif, ticket non archive) ;
2. arguments ;
3. etat : la transition est-elle permise dans l'etat courant ? (patron State) ;
4. regle contextuelle : auteur, assigne, visibilite ;
5. effet, puis mise a jour de la date de modification.
Un refus renvoie False ou None, sans aucun effet, et son motif va dans le journal.

Chaque action passe par un essai prive (__try_x) qui suit cet ordre. Avec
apply=False, l'essai ne fait que repondre « serait-ce permis ? », sans effet ni
motif : allowed_actions s'en sert, il n'y a donc qu'une seule copie des regles.
"""
import logging
import os
from datetime import datetime
from enum import Enum
from typing import Optional

from .._texte import normaliser, texte_valide
from ..acteurs import Permission, User, UserRegistry
from .contenus import Content
from .etats import OpenState, Status, TicketState
from .fichiers import ContentFactory
from .visiteur import ExportVisitor, TicketVisitor, ViewVisitor

_journal = logging.getLogger(__name__)
_TITRE_MAX = 200
_TEXTE_MAX = 5000  # commentaires et motifs
_LECTURE_SEULE = (Permission.VIEW, Permission.EXPORT)  # seules actions permises sur une archive
_ARCHIVABLES = (Status.TERMINE, Status.FERME)


def _refus(motif: str, valeur=False, apply: bool = True):
    if apply:
        _journal.info("refus : %s", motif)
    return valeur


def _texte_valide(texte: object, maximum: int, multiligne: bool = False) -> bool:
    """Voir gestion_tickets._texte : non vide, borne, rien qui puisse falsifier l'affichage."""
    return texte_valide(texte, maximum, multiligne)


class Priority(Enum):
    BASSE = "BASSE"
    NORMALE = "NORMALE"
    HAUTE = "HAUTE"


class Comment:
    """Un message ajoute a un ticket. Il n'est jamais modifie ni supprime."""

    def __init__(self, id: int, author: User, text: str) -> None:
        # Constructeur de paquetage (~) : seul Ticket cree des commentaires.
        self.__comment_id = id
        self.__author = author
        self.__text = text
        self.__posted_at = datetime.now()

    @property
    def comment_id(self) -> int:
        return self.__comment_id

    @property
    def text(self) -> str:
        return self.__text

    @property
    def posted_at(self) -> datetime:
        return self.__posted_at

    def get_author(self) -> User:
        return self.__author

    def _accept(self, v: TicketVisitor) -> None:
        v.visit_comment(self)

    def __repr__(self) -> str:
        return f"Comment#{self.__comment_id} de {self.__author.name} : {self.__text}"


class Ticket:
    """Un signalement et son cycle de vie."""

    def __init__(self, id: int, author: User, title: str, p: Priority, users: UserRegistry) -> None:
        # Constructeur de paquetage (~) : seul TicketRegistry cree des tickets.
        maintenant = datetime.now()
        self.__ticket_id = id
        self.__title = title
        self.__priority = p
        self.__creation_date = maintenant
        self.__update_date = maintenant
        self.__archive_date = None
        self.__next_comment_id = 1
        self.__users = users             # association comptes (1) : qui a le droit d'agir
        self.__author = author           # association author (1)
        self.__assignee = None           # association assignee (0..1)
        self.__state = OpenState()       # association state (1)
        self.__comments = []             # composition comments
        self.__description = []          # composition description

    # ------------------------------------------------ accesseurs en lecture (legende)
    @property
    def ticket_id(self) -> int:
        return self.__ticket_id

    @property
    def title(self) -> str:
        return self.__title

    @property
    def priority(self) -> Priority:
        return self.__priority

    @property
    def creation_date(self) -> datetime:
        return self.__creation_date

    @property
    def update_date(self) -> datetime:
        return self.__update_date

    @property
    def archive_date(self) -> Optional[datetime]:
        return self.__archive_date

    @property
    def next_comment_id(self) -> int:
        return self.__next_comment_id

    # ------------------------------------------------ controles prives
    def __authorize(self, actor: User, p: Permission, apply: bool = True) -> bool:
        """Droit global : permission du role, compte actif ; une archive est en lecture seule."""
        if not self.__users.contains(actor):
            return _refus(f"{p.value} : acteur inconnu du registre des comptes", apply=apply)
        if not actor.can_globally(p):
            return _refus(f"{p.value} : permission absente ou compte desactive", apply=apply)
        if self.__archive_date is not None and p not in _LECTURE_SEULE:
            return _refus(f"ticket #{self.__ticket_id} archive : lecture et export seulement", apply=apply)
        return True

    def __is_author(self, u: User) -> bool:
        """Regle contextuelle : u est-il l'auteur ?"""
        return u is self.__author

    def __accept(self, v: TicketVisitor) -> None:
        """Parcours complet : le ticket, sa description, puis ses commentaires."""
        v.visit_ticket(self)
        for contenu in self.__description:
            contenu._accept(v)
        for commentaire in self.__comments:
            commentaire._accept(v)

    def __append_comment(self, author: User, text: str) -> Comment:
        commentaire = Comment(self.__next_comment_id, author, normaliser(text).strip())
        self.__comments.append(commentaire)
        self.__next_comment_id += 1
        return commentaire

    # ------------------------------------------------ mutateurs de paquetage (~)
    def _set_state(self, s: TicketState) -> None:
        self.__state = s

    def _set_assignee(self, u: Optional[User]) -> None:
        self.__assignee = u

    def _mark_archived(self) -> None:
        self.__archive_date = datetime.now()
        self._touch()

    def _touch(self) -> None:
        self.__update_date = datetime.now()

    # ------------------------------------------------ essais (une seule copie des regles)
    # apply=True : verifie, journalise le motif d'un refus et, pour une transition,
    # laisse l'etat l'appliquer. apply=False : verifie seulement, sans effet ni motif ;
    # les arguments ne sont alors pas encore connus et ne sont pas controles.
    def __try_assign(self, actor, assignee, apply) -> bool:
        if not self.__authorize(actor, Permission.ASSIGN, apply):
            return False
        if apply and (not self.__users.contains(assignee) or not assignee.can_globally(Permission.SUBMIT)):
            return _refus("l'assigne doit etre un developpeur actif du registre")
        return self.__state._assign(self, actor, assignee, apply)

    def __try_transition(self, actor, permission, transition, apply) -> bool:
        return self.__authorize(actor, permission, apply) and transition(self, actor, apply=apply)

    def __try_with_reason(self, actor, permission, action, reason, transition, apply) -> bool:
        if not self.__authorize(actor, permission, apply):
            return False
        if apply and not _texte_valide(reason, _TEXTE_MAX, multiligne=True):
            return _refus(f"{action} : un motif est obligatoire")
        return transition(self, actor, reason, apply=apply)

    def __try_edit(self, actor, title, apply) -> bool:
        if not self.__authorize(actor, Permission.EDIT, apply):
            return False
        if apply and not _texte_valide(title, _TITRE_MAX):
            return _refus(f"titre vide, sur plusieurs lignes ou de plus de {_TITRE_MAX} caracteres")
        if not self.__state.allows_edit():
            return _refus(f"ticket non modifiable en {self.get_status().value}", apply=apply)
        if not self.__is_author(actor):
            return _refus("seul l'auteur modifie son ticket", apply=apply)
        return True

    def __try_set_priority(self, actor, p, apply) -> bool:
        if not self.__authorize(actor, Permission.SET_PRIORITY, apply):
            return False
        if apply and not isinstance(p, Priority):
            return _refus(f"priorite invalide : {p!r}")
        if apply and p is self.__priority:
            return _refus(f"la priorite est deja {p.value}")
        return True

    def __try_comment(self, author, text, apply) -> bool:
        if not self.__authorize(author, Permission.COMMENT, apply):
            return False
        if not self.is_visible_to(author):
            return _refus("commentaire sur un ticket invisible pour l'auteur", apply=apply)
        if apply and not _texte_valide(text, _TEXTE_MAX, multiligne=True):
            return _refus(f"commentaire vide, de plus de {_TEXTE_MAX} caracteres ou avec un caractere de controle")
        return True

    def __try_attach(self, actor, c, apply) -> bool:
        if not self.__authorize(actor, Permission.ATTACH, apply):
            return False
        if apply and not isinstance(c, Content):
            return _refus("ce n'est pas un contenu")
        if not self.__state.allows_edit():
            return _refus(f"ticket non modifiable en {self.get_status().value}", apply=apply)
        if not self.__is_author(actor):
            return _refus("seul l'auteur complete la description", apply=apply)
        return True

    def __try_read(self, actor, p, apply) -> bool:
        """VIEW ou EXPORT : droit global puis visibilite."""
        if not self.__authorize(actor, p, apply):
            return False
        if not self.is_visible_to(actor):
            verbe = "consultation" if p is Permission.VIEW else "export"
            return _refus(f"{verbe} d'un ticket invisible pour l'acteur", apply=apply)
        return True

    def _try_archive(self, actor: User, apply: bool = True) -> bool:
        """Regles d'etat de l'archivage ; le droit ARCHIVE est verifie par l'appelant."""
        if self.__archive_date is not None:
            return _refus(f"ticket #{self.__ticket_id} deja archive", apply=apply)
        if self.get_status() not in _ARCHIVABLES:
            return _refus(f"ticket #{self.__ticket_id} en {self.get_status().value} : "
                          "seul TERMINE ou FERME s'archive", apply=apply)
        return True

    def allowed_actions(self, actor: User) -> frozenset:
        """Permissions que l'acteur pourrait exercer maintenant sur ce ticket, avec des
        arguments valides. Memes essais que les actions : aucune regle recopiee, aucun effet."""
        P = Permission
        essais = {
            P.VIEW: lambda: self.__try_read(actor, P.VIEW, False),
            P.EXPORT: lambda: self.__try_read(actor, P.EXPORT, False),
            P.COMMENT: lambda: self.__try_comment(actor, None, False),
            P.EDIT: lambda: self.__try_edit(actor, None, False),
            P.ATTACH: lambda: self.__try_attach(actor, None, False),
            P.ASSIGN: lambda: self.__try_assign(actor, None, False),
            P.SUBMIT: lambda: self.__try_transition(actor, P.SUBMIT, self.__state._submit, False),
            P.VALIDATE: lambda: self.__try_transition(actor, P.VALIDATE, self.__state._validate, False),
            P.REJECT: lambda: self.__try_with_reason(actor, P.REJECT, "Rejet", None, self.__state._reject, False),
            P.CLOSE: lambda: self.__try_with_reason(actor, P.CLOSE, "Fermeture", None, self.__state._close, False),
            P.REOPEN: lambda: self.__try_with_reason(actor, P.REOPEN, "Reouverture", None, self.__state._reopen, False),
            P.SET_PRIORITY: lambda: self.__try_set_priority(actor, None, False),
            P.ARCHIVE: lambda: self.__authorize(actor, P.ARCHIVE, False) and self._try_archive(actor, False),
        }
        return frozenset(p for p, essai in essais.items() if essai())

    # ------------------------------------------------ transitions du cycle de vie
    def assign(self, actor: User, assignee: User) -> bool:
        """ASSIGN ; l'assigne doit pouvoir soumettre (developpeur actif)."""
        if not self.__try_assign(actor, assignee, True):
            return False
        self._touch()
        return True

    def submit(self, actor: User) -> bool:
        if not self.__try_transition(actor, Permission.SUBMIT, self.__state._submit, True):
            return False
        self._touch()
        return True

    def validate(self, actor: User) -> bool:
        if not self.__try_transition(actor, Permission.VALIDATE, self.__state._validate, True):
            return False
        self._touch()
        return True

    def reject(self, actor: User, reason: str) -> bool:
        """REJECT ; retour a ASSIGNE, motif ajoute en commentaire."""
        return self.__avec_motif(actor, Permission.REJECT, "Rejet", reason, self.__state._reject)

    def close(self, actor: User, reason: str) -> bool:
        """CLOSE ; vers FERME, motif ajoute en commentaire."""
        return self.__avec_motif(actor, Permission.CLOSE, "Fermeture", reason, self.__state._close)

    def reopen(self, actor: User, reason: str) -> bool:
        """REOPEN ; vers OUVERT sans assigne, motif ajoute en commentaire."""
        return self.__avec_motif(actor, Permission.REOPEN, "Reouverture", reason, self.__state._reopen)

    def __avec_motif(self, actor, permission, action, reason, transition) -> bool:
        if not self.__try_with_reason(actor, permission, action, reason, transition, True):
            return False
        self.__append_comment(actor, f"{action} : {normaliser(reason).strip()}")
        self._touch()
        return True

    # ------------------------------------------------ autres actions
    def edit(self, actor: User, title: str) -> bool:
        """EDIT ; reserve a l'auteur, tant que l'etat le permet."""
        if not self.__try_edit(actor, title, True):
            return False
        self.__title = title.strip()
        self._touch()
        return True

    def set_priority(self, actor: User, p: Priority) -> bool:
        if not self.__try_set_priority(actor, p, True):
            return False
        self.__priority = p
        self._touch()
        return True

    def add_comment(self, author: User, text: str) -> Optional[Comment]:
        """COMMENT et visibilite ; permis meme sur un ticket ferme, jamais sur une archive."""
        if not self.__try_comment(author, text, True):
            return None
        commentaire = self.__append_comment(author, text)
        self._touch()
        return commentaire

    def add_content(self, actor: User, c: Content) -> bool:
        """ATTACH ; reserve a l'auteur, tant que l'etat le permet. Le contenu repasse
        par la fabrique : un contenu construit a la main hors de UPLOAD_DIR est refuse."""
        if not self.__try_attach(actor, c, True):
            return False
        # On rejoue la fabrique : le contenu joint est celui qu'elle produit, jamais l'objet recu.
        verifie = ContentFactory.from_path(c.path) if isinstance(c.path, str) else None
        if (verifie is None or type(verifie) is not type(c)
                or os.path.normcase(os.path.realpath(c.path)) != os.path.normcase(verifie.path)):
            return _refus(f"contenu non valide ou hors du dossier autorise : {c.path!r}")
        if any(os.path.normcase(d.path) == os.path.normcase(verifie.path) for d in self.__description):
            return _refus(f"fichier deja joint : {os.path.basename(verifie.path)}")
        self.__description.append(verifie)
        self._touch()
        return True

    def consult(self, actor: User, v: ViewVisitor) -> bool:
        """VIEW et visibilite ; le type du visiteur fixe la permission exigee."""
        if not isinstance(v, ViewVisitor) or isinstance(v, ExportVisitor):
            return _refus("consulter exige un ViewVisitor qui ne soit pas aussi un ExportVisitor")
        if not self.__try_read(actor, Permission.VIEW, True):
            return False
        self.__accept(v)
        return True

    def export(self, actor: User, v: ExportVisitor) -> bool:
        """EXPORT et visibilite."""
        if not isinstance(v, ExportVisitor) or isinstance(v, ViewVisitor):
            return _refus("exporter exige un ExportVisitor qui ne soit pas aussi un ViewVisitor")
        if not self.__try_read(actor, Permission.EXPORT, True):
            return False
        self.__accept(v)
        return True

    # ------------------------------------------------ lectures
    def get_status(self) -> Status:
        return self.__state.name()

    def get_author(self) -> User:
        return self.__author

    def get_assignee(self) -> Optional[User]:
        return self.__assignee

    def is_archived(self) -> bool:
        return self.__archive_date is not None

    def is_visible_to(self, u: User) -> bool:
        """Compte du registre qui est l'auteur, l'assigne, ou detenteur de VIEW_ALL."""
        return self.__users.contains(u) and (u is self.__author or u is self.__assignee
                                             or u.can_globally(Permission.VIEW_ALL))

    def __repr__(self) -> str:
        archive = ", archive" if self.is_archived() else ""
        return f"Ticket#{self.__ticket_id} [{self.get_status().value}{archive}] {self.__title}"
