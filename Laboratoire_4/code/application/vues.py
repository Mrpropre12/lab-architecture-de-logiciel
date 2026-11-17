"""Les vues sont definies dans le contrat partage (labo 4) ; reexportees ici pour
les modules du labo 3 qui les importaient d'application.vues."""
from contrat import CompteVue, DetailTicket, LigneTicket, Profil

__all__ = ["LigneTicket", "DetailTicket", "CompteVue", "Profil"]
