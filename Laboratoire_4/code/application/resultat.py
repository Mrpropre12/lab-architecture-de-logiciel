"""Capture du motif d'un refus. Resultat est defini dans le contrat partage (labo 4)."""
import logging
from typing import Optional

from contrat import Resultat  # noqa: F401  (reexporte pour les modules du labo 3)

_PREFIXE = "refus : "


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
