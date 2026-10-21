"""Etat de l'application : les deux registres (registre des comptes injecte dans
celui des tickets, comme au labo 2) et le compte connecte."""
from typing import Optional

from gestion_tickets.acteurs import Permission, User, UserRegistry
from gestion_tickets.ticket import TicketRegistry


class Session:

    def __init__(self, users: UserRegistry, tickets: TicketRegistry) -> None:
        self.__users = users
        self.__tickets = tickets
        self.__connecte: Optional[User] = None

    @property
    def users(self) -> UserRegistry:
        return self.__users

    @property
    def tickets(self) -> TicketRegistry:
        return self.__tickets

    @property
    def connecte(self) -> Optional[User]:
        """Compte obtenu par UserRegistry.authenticate, ou None."""
        return self.__connecte

    def ouvrir(self, compte: User) -> None:
        self.__connecte = compte

    def fermer(self) -> None:
        self.__connecte = None

    def peut(self, p: Permission) -> bool:
        """Droit global du compte connecte (pour cacher les menus hors de ses roles).
        Le modele reverifie chaque action : ce n'est qu'un confort d'affichage."""
        return self.__connecte is not None and self.__connecte.can_globally(p)
