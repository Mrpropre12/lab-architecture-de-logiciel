"""Ce que le serveur garde en memoire : le modele, et rien de propre a une conversation.

Chaque requete arrive avec son jeton ; le controleur demande ici des services ouverts
sur le compte du jeton, le temps d'un appel. Un verrou unique entoure chaque appel au
modele : FastAPI execute les routes dans plusieurs fils, le modele n'est pas prevu pour
cela, et CaptureMotif ecoute un journal partage (deux requetes melangeraient leurs motifs).
"""
import threading
from contextlib import contextmanager
from typing import Dict, Iterator, Optional, Tuple

from application import ImportFichiers, ServiceComptes, ServiceTickets, Session
from gestion_tickets.acteurs import User, UserRegistry
from gestion_tickets.ticket import TicketRegistry


class Noyau:

    def __init__(self, users: UserRegistry, tickets: TicketRegistry, dossier_televersement: str) -> None:
        self.__users = users
        self.__tickets = tickets
        self.__dossier = dossier_televersement
        self.__verrou = threading.Lock()
        # Comptes deja authentifies, par numero : le jeton ne porte que le numero, et le modele
        # ne rend un User qu'a authenticate. Ce n'est pas un etat de session : aucune requete
        # ne depend d'une requete precedente, sinon de la connexion qui a emis le jeton.
        self.__authentifies: Dict[int, User] = {}

    @contextmanager
    def services(self, compte: Optional[User] = None) -> Iterator[Tuple[Session, ServiceComptes, ServiceTickets]]:
        """Services ouverts sur compte (ou sans compte), sous le verrou, pour un seul appel."""
        with self.__verrou:
            session = Session(self.__users, self.__tickets)
            if compte is not None:
                session.ouvrir(compte)
            yield session, ServiceComptes(session), ServiceTickets(session, ImportFichiers(self.__dossier))

    def connecter(self, courriel: str, mot_de_passe: str):
        """Resultat de la connexion, et le compte authentifie (None si refus)."""
        with self.services() as (session, comptes, _):
            r = comptes.connecter(courriel, mot_de_passe)
            compte = session.connecte
            if r.ok:
                self.__authentifies[compte.user_id] = compte
        return r, compte

    def compte(self, numero: int) -> Optional[User]:
        """Le compte authentifie de ce numero, s'il est encore actif."""
        with self.__verrou:
            compte = self.__authentifies.get(numero)
            return compte if compte is not None and compte.active else None
