"""Couche application (labo 3) : entre l'interface graphique et le modele du labo 2.

Aucun import de Qt ici. L'interface n'importe que ce paquet : les enumerations
et les blocs dont elle a besoin pour afficher sont reexportes ci-dessous.
"""
from gestion_tickets.acteurs import Permission
from gestion_tickets.consultation import BlocCommentaire, BlocImage, BlocTexte, BlocTicket, BlocVideo
from gestion_tickets.ticket import Priority, Status

from .fichiers import EXTENSIONS_IMAGES, ImportFichiers
from .resultat import CaptureMotif, Resultat
from .services import ASSIGNES_A_MOI, MES_TICKETS, ROLES, TOUS, ServiceComptes, ServiceTickets
from .session import Session
from .vues import CompteVue, DetailTicket, LigneTicket, Profil

__all__ = ["Permission", "Priority", "Status", "BlocTicket", "BlocTexte", "BlocImage", "BlocVideo",
           "BlocCommentaire", "ImportFichiers", "EXTENSIONS_IMAGES", "CaptureMotif", "Resultat",
           "ServiceComptes", "ServiceTickets", "MES_TICKETS", "TOUS", "ASSIGNES_A_MOI", "ROLES", "Session",
           "LigneTicket", "DetailTicket", "CompteVue", "Profil", "creer_application"]


def creer_application(users, tickets, dossier_televersement):
    """Assemble la session et les services (injection des dependances)."""
    session = Session(users, tickets)
    return session, ServiceComptes(session), ServiceTickets(session, ImportFichiers(dossier_televersement))
