"""Contrat partage (labo 4) : ce que le client et le serveur echangent.

Aucun import du modele, de l'application, de Qt ni du reseau. Le serveur traduit le
modele vers ces types (application/traduction.py) ; le client les reconstruit depuis
le JSON (client/). L'interface graphique n'importe que ce paquet : elle fonctionne donc
de la meme facon avec les services locaux et avec l'API.
"""
from .blocs import BlocCommentaire, BlocImage, BlocTexte, BlocTicket, BlocVideo
from .enumerations import (ASSIGNES_A_MOI, EXTENSIONS_IMAGES, MES_TICKETS, ROLES, TOUS, Permission, Priority,
                           Status)
from .interfaces import GestionComptes, GestionTickets
from .resultat import Cause, Resultat
from .vues import CompteVue, DetailTicket, LigneTicket, Profil

__all__ = ["Permission", "Priority", "Status", "MES_TICKETS", "TOUS", "ASSIGNES_A_MOI", "ROLES",
           "EXTENSIONS_IMAGES", "BlocTicket", "BlocTexte", "BlocImage", "BlocVideo", "BlocCommentaire",
           "Cause", "Resultat", "GestionComptes", "GestionTickets", "LigneTicket", "DetailTicket", "CompteVue", "Profil"]
