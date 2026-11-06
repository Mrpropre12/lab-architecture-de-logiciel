"""Resultat d'un geste de l'utilisateur, avec la cause d'un refus."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class Cause(Enum):
    """Pourquoi un geste a ete refuse. Fixee par les services, la ou l'information existe ;
    le serveur en tire le code HTTP sans recopier aucune regle."""
    NON_CONNECTE = "NON_CONNECTE"  # aucun compte connecte, jeton invalide, identifiants faux
    INTROUVABLE = "INTROUVABLE"    # ticket ou compte inexistant ou invisible pour ce compte
    INTERDIT = "INTERDIT"          # les roles du compte n'accordent pas la permission
    CONFLIT = "CONFLIT"            # permission accordee, mais l'etat de la cible ne le permet pas
    INVALIDE = "INVALIDE"          # argument refuse (texte vide, fichier refuse, filtre inconnu)
    INJOIGNABLE = "INJOIGNABLE"    # client seulement : le serveur ne repond pas


@dataclass(frozen=True)
class Resultat:
    """Ce que l'interface affiche apres une action : OK, ou REFUSE avec le motif du modele.

    valeur : ce que l'action produit (un numero de ticket, une liste...).
    details : remarques secondaires, par exemple une piece jointe refusee
    alors que le ticket, lui, a bien ete cree.
    cause : la nature du refus (None en cas de succes).
    """
    ok: bool
    motif: Optional[str] = None
    valeur: object = None
    details: Tuple[str, ...] = field(default_factory=tuple)
    cause: Optional[Cause] = None

    @classmethod
    def succes(cls, valeur=None, details=()) -> "Resultat":
        return cls(True, None, valeur, tuple(details))

    @classmethod
    def echec(cls, motif: str, details=(), cause: Cause = Cause.INVALIDE) -> "Resultat":
        return cls(False, motif, None, tuple(details), cause)
