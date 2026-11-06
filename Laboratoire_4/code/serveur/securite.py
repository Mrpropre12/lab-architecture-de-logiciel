"""Jetons d'acces signes (JWT, HS256). REST est sans etat : chaque requete porte son jeton.

Le jeton contient le numero du compte et sa date d'expiration ; sa signature prouve qu'il
a ete emis par ce serveur. Il ne peut pas etre revoque avant son expiration : se
deconnecter consiste a l'oublier cote client. D'ou une duree courte.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt

ALGORITHME = "HS256"


class Jetons:

    def __init__(self, secret: Optional[str] = None, duree: timedelta = timedelta(hours=8)) -> None:
        """secret : variable d'environnement en production ; sinon un secret aleatoire,
        et les jetons ne survivent pas a un redemarrage (les donnees non plus).
        HS256 exige une cle d'au moins 32 octets (RFC 7518, section 3.2)."""
        if secret is not None and len(secret.encode("utf-8")) < 32:
            raise ValueError("TICKETS_SECRET doit compter au moins 32 octets")
        self.__secret = secret or secrets.token_urlsafe(32)
        self.__duree = duree

    def emettre(self, numero: int) -> Tuple[str, datetime]:
        maintenant = datetime.now(timezone.utc)
        expire = maintenant + self.__duree
        jeton = jwt.encode({"sub": str(numero), "iat": maintenant, "exp": expire}, self.__secret, ALGORITHME)
        return jeton, expire

    def lire(self, jeton: str) -> Optional[int]:
        """Numero du compte, ou None si le jeton est invalide, falsifie ou expire."""
        try:
            contenu = jwt.decode(jeton, self.__secret, algorithms=[ALGORITHME], options={"require": ["sub", "exp"]})
            return int(contenu["sub"])
        except (jwt.InvalidTokenError, ValueError):
            return None
