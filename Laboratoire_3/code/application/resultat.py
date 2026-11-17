"""Resultat d'un geste de l'utilisateur, et capture du motif d'un refus."""
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

_PREFIXE = "refus : "


@dataclass(frozen=True)
class Resultat:
    """Ce que l'interface affiche apres une action : OK, ou REFUSE avec le motif du modele.

    valeur : ce que l'action produit (un numero de ticket, une liste...).
    details : remarques secondaires, par exemple une piece jointe refusee
    alors que le ticket, lui, a bien ete cree.
    """
    ok: bool
    motif: Optional[str] = None
    valeur: object = None
    details: Tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def succes(cls, valeur=None, details=()) -> "Resultat":
        return cls(True, None, valeur, tuple(details))

    @classmethod
    def echec(cls, motif: str, details=()) -> "Resultat":
        return cls(False, motif, None, tuple(details))


class CaptureMotif(logging.Handler):
    """Recueille, le temps d'un appel, les motifs que le modele ecrit dans son journal.

    Le modele garde sa convention du labo 2 (False, None ou liste vide, motif au
    journal) : c'est ici, et seulement ici, que le motif est relu.

        with CaptureMotif() as capture:
            ok = ticket.validate(acteur)
        capture.motif   # dernier motif, sans le prefixe technique « refus : »
    """

    JOURNAL = "gestion_tickets"

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.messages = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())

    def __enter__(self) -> "CaptureMotif":
        journal = logging.getLogger(self.JOURNAL)
        self.__niveau = journal.level
        journal.addHandler(self)
        if journal.getEffectiveLevel() > logging.INFO:
            journal.setLevel(logging.INFO)
        return self

    def __exit__(self, *exc) -> None:
        journal = logging.getLogger(self.JOURNAL)
        journal.removeHandler(self)
        journal.setLevel(self.__niveau)

    @property
    def motif(self) -> Optional[str]:
        if not self.messages:
            return None
        dernier = self.messages[-1]
        return dernier[len(_PREFIXE):] if dernier.startswith(_PREFIXE) else dernier

    def motif_ou(self, defaut: str) -> str:
        return self.motif or defaut
