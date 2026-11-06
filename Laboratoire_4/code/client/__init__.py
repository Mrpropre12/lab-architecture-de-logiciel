"""Client de l'API REST (labo 4) : la vue du MVC distribue parle au serveur par HTTP.

ClientComptes et ClientTickets ont les memes methodes que les services de la couche
application et rendent les memes types du contrat. Ce paquet n'importe ni le modele, ni
l'application, ni Qt : seulement le contrat et httpx.
"""
from .images import CacheImages
from .services import ClientComptes, ClientTickets
from .transport import Transport

__all__ = ["Transport", "CacheImages", "ClientComptes", "ClientTickets", "creer_clients"]


def creer_clients(url: str = None, http=None):
    """Transport, ClientComptes et ClientTickets pour le serveur url (ou un client http deja construit)."""
    transport = Transport(url, http)
    return transport, ClientComptes(transport), ClientTickets(transport, CacheImages(transport))
