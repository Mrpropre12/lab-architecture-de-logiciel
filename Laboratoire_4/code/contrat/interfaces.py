"""Ce que l'interface graphique attend des services, sans savoir ou ils s'executent.

Deux implementations de chaque interface :
- ServiceComptes et ServiceTickets (application) : le modele dans ce processus ;
- ClientComptes et ClientTickets (client) : le modele sur le serveur, par l'API REST.
L'interface depend de cette abstraction, pas de l'une ou l'autre (inversion des dependances) ;
main.py choisit laquelle injecter. Chaque methode rend un Resultat du contrat.
"""
from abc import ABC, abstractmethod
from typing import Iterable

from .resultat import Resultat


class GestionComptes(ABC):

    @abstractmethod
    def connecter(self, courriel: str, mot_de_passe: str) -> Resultat:
        """valeur : le Profil du compte connecte."""

    @abstractmethod
    def deconnecter(self) -> Resultat: ...

    @abstractmethod
    def inscrire(self, nom: str, courriel: str, mot_de_passe: str, confirmation: str) -> Resultat:
        """valeur : le nom du compte cree (role Rapporteur)."""

    @abstractmethod
    def profil(self) -> Resultat: ...

    @abstractmethod
    def lister(self) -> Resultat:
        """valeur : liste de CompteVue (MANAGE_USERS)."""

    @abstractmethod
    def attribuer_role(self, numero: int, nom_role: str) -> Resultat: ...

    @abstractmethod
    def retirer_role(self, numero: int, nom_role: str) -> Resultat: ...

    @abstractmethod
    def desactiver(self, numero: int) -> Resultat: ...

    @abstractmethod
    def reactiver(self, numero: int) -> Resultat: ...


class GestionTickets(ABC):

    @abstractmethod
    def lister(self, filtre: str, statut=None, priorite=None) -> Resultat:
        """valeur : liste de LigneTicket."""

    @abstractmethod
    def archives(self) -> Resultat: ...

    @abstractmethod
    def assignables(self) -> Resultat: ...

    @abstractmethod
    def detail(self, numero: int) -> Resultat:
        """valeur : DetailTicket (blocs a afficher, actions permises maintenant)."""

    @abstractmethod
    def actions_permises(self, numero: int) -> frozenset: ...

    @abstractmethod
    def creer(self, titre: str, priorite, texte: str = "", images: Iterable[str] = ()) -> Resultat:
        """valeur : le numero du ticket ; details : les pieces refusees."""

    @abstractmethod
    def ajouter_texte(self, numero: int, texte: str) -> Resultat: ...

    @abstractmethod
    def joindre_image(self, numero: int, chemin_source: str) -> Resultat: ...

    @abstractmethod
    def modifier_titre(self, numero: int, titre: str) -> Resultat: ...

    @abstractmethod
    def commenter(self, numero: int, texte: str) -> Resultat:
        """valeur : le BlocCommentaire publie."""

    @abstractmethod
    def assigner(self, numero: int, numero_assigne: int) -> Resultat: ...

    @abstractmethod
    def soumettre(self, numero: int) -> Resultat: ...

    @abstractmethod
    def valider(self, numero: int) -> Resultat: ...

    @abstractmethod
    def rejeter(self, numero: int, motif: str) -> Resultat: ...

    @abstractmethod
    def fermer(self, numero: int, motif: str) -> Resultat: ...

    @abstractmethod
    def rouvrir(self, numero: int, motif: str) -> Resultat: ...

    @abstractmethod
    def changer_priorite(self, numero: int, priorite) -> Resultat: ...

    @abstractmethod
    def archiver(self, numero: int) -> Resultat: ...
