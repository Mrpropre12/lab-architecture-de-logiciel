"""Couche application (labo 3) : entre l'interface graphique et le modele du labo 2.

Aucun import de Qt ici. Depuis le labo 4, les types echanges (enumerations, blocs,
vues, Resultat) viennent du contrat partage : ils sont reexportes ci-dessous pour
les modules et les tests du labo 3.
"""
from contrat import (ASSIGNES_A_MOI, EXTENSIONS_IMAGES, MES_TICKETS, ROLES, TOUS, BlocCommentaire, BlocImage,
                     BlocTexte, BlocTicket, BlocVideo, Cause, CompteVue, DetailTicket, LigneTicket, Permission,
                     Priority, Profil, Resultat, Status)

from .fichiers import ImportFichiers
from .resultat import CaptureMotif
from .services import ServiceComptes, ServiceTickets
from .session import Session

__all__ = ["Permission", "Priority", "Status", "BlocTicket", "BlocTexte", "BlocImage", "BlocVideo",
           "BlocCommentaire", "ImportFichiers", "EXTENSIONS_IMAGES", "CaptureMotif", "Resultat", "Cause",
           "ServiceComptes", "ServiceTickets", "MES_TICKETS", "TOUS", "ASSIGNES_A_MOI", "ROLES", "Session",
           "LigneTicket", "DetailTicket", "CompteVue", "Profil", "creer_application"]


def creer_application(users, tickets, dossier_televersement):
    """Assemble la session et les services (injection des dependances)."""
    session = Session(users, tickets)
    return session, ServiceComptes(session), ServiceTickets(session, ImportFichiers(dossier_televersement))
