"""Serveur REST (labo 4) : le controleur du MVC.

Il expose les services de la couche application par HTTP et JSON, sans aucune regle
metier propre. Il ne depend ni de l'interface, ni du client, ni de Qt.
"""
from .app import creer_api, creer_api_demo

__all__ = ["creer_api", "creer_api_demo"]
