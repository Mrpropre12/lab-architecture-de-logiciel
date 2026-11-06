"""Services distants : memes methodes et memes Resultat que ServiceComptes et ServiceTickets
de la couche application, mais chaque geste devient une requete a l'API REST.

L'interface graphique recoit ces objets a la place des services locaux (main.py --serveur)
et ne voit aucune difference : c'est le patron Proxy, rendu possible par le contrat partage.
Aucune regle metier ici non plus : le serveur, donc le modele, decide de tout.
"""
import os
from typing import Iterable
from urllib.parse import quote

from contrat import MES_TICKETS, GestionComptes, GestionTickets, Resultat

from . import conversion
from .images import CacheImages
from .transport import DELAI_TELEVERSEMENT, NON_CONNECTE, Transport

LIMITE_IMAGE = 10 * 1024 * 1024  # inutile d'envoyer une image que le serveur refusera


def _ou(r: Resultat, transformer) -> Resultat:
    """Applique transformer a la valeur d'un Resultat accepte."""
    return Resultat.succes(transformer(r.valeur), r.details) if r.ok else r


class ClientComptes(GestionComptes):

    def __init__(self, transport: Transport) -> None:
        self.__t = transport

    # ------------------------------------------------ connexion
    def reveiller(self) -> Resultat:
        """Propre au client : reveille le serveur avant la premiere connexion."""
        return self.__t.reveiller()

    def connecter(self, courriel: str, mot_de_passe: str) -> Resultat:
        self.__t.fermer()
        r = self.__t.requete("POST", "/sessions", json={"courriel": courriel, "mot_de_passe": mot_de_passe})
        if not r.ok:
            return r
        profil = conversion.profil(r.valeur["profil"])
        self.__t.ouvrir(r.valeur["jeton"], profil)
        return Resultat.succes(profil)

    def deconnecter(self) -> Resultat:
        self.__t.fermer()
        return Resultat.succes()

    def inscrire(self, nom: str, courriel: str, mot_de_passe: str, confirmation: str) -> Resultat:
        r = self.__t.requete("POST", "/comptes", json={"nom": nom, "courriel": courriel, "mot_de_passe": mot_de_passe,
                                                       "confirmation": confirmation})
        return _ou(r, lambda j: j["nom"])

    # ------------------------------------------------ lecture
    def profil(self) -> Resultat:
        if not self.__t.connecte:
            return NON_CONNECTE
        r = _ou(self.__t.requete("GET", "/moi"), conversion.profil)
        if r.ok:
            self.__t.retenir(r.valeur)
        return r

    def lister(self) -> Resultat:
        if not self.__t.connecte:
            return NON_CONNECTE
        return _ou(self.__t.requete("GET", "/comptes"), lambda j: [conversion.compte(c) for c in j])

    # ------------------------------------------------ gestion (MANAGE_USERS)
    def __gerer(self, numero: int, methode: str, chemin: str, **kwargs) -> Resultat:
        if not self.__t.connecte:
            return NON_CONNECTE
        moi = self.__t.profil.numero if self.__t.profil else None
        r = self.__t.requete(methode, chemin, **kwargs)
        if not r.ok:
            return r
        details = tuple(r.valeur.get("details", ())) if r.valeur else ()
        if methode == "PATCH" and numero == moi and kwargs["json"]["actif"] is False:
            self.__t.fermer()  # le compte s'est desactive lui-meme : son jeton ne vaut plus rien
        return Resultat.succes(r.valeur["nom"] if r.valeur else None, details)

    def attribuer_role(self, numero: int, nom_role: str) -> Resultat:
        return self.__gerer(numero, "POST", f"/comptes/{numero}/roles", json={"role": nom_role})

    def retirer_role(self, numero: int, nom_role: str) -> Resultat:
        return self.__gerer(numero, "DELETE", f"/comptes/{numero}/roles/{quote(nom_role, safe='')}")

    def desactiver(self, numero: int) -> Resultat:
        return self.__gerer(numero, "PATCH", f"/comptes/{numero}", json={"actif": False})

    def reactiver(self, numero: int) -> Resultat:
        return self.__gerer(numero, "PATCH", f"/comptes/{numero}", json={"actif": True})


class ClientTickets(GestionTickets):

    def __init__(self, transport: Transport, images: CacheImages = None) -> None:
        self.__t = transport
        self.__images = images or CacheImages(transport)

    def __si_connecte(self, methode: str, chemin: str, **kwargs) -> Resultat:
        return self.__t.requete(methode, chemin, **kwargs) if self.__t.connecte else NON_CONNECTE

    def __transition(self, numero: int, action: str, **corps) -> Resultat:
        r = self.__si_connecte("POST", f"/tickets/{numero}/transitions", json={"action": action, **corps})
        return _ou(r, lambda _: True)

    # ------------------------------------------------ listes
    def lister(self, filtre: str = MES_TICKETS, statut=None, priorite=None) -> Resultat:
        params = {"filtre": filtre}
        if statut is not None:
            params["statut"] = statut.value
        if priorite is not None:
            params["priorite"] = priorite.value
        return _ou(self.__si_connecte("GET", "/tickets", params=params), lambda j: [conversion.ligne(l) for l in j])

    def archives(self) -> Resultat:
        return _ou(self.__si_connecte("GET", "/archives"), lambda j: [conversion.ligne(l) for l in j])

    def assignables(self) -> Resultat:
        r = self.__si_connecte("GET", "/comptes", params={"assignables": "true"})
        return _ou(r, lambda j: [conversion.compte(c) for c in j])

    # ------------------------------------------------ detail
    def detail(self, numero: int) -> Resultat:
        """Blocs et actions permises ; les images sont telechargees dans le cache local."""
        r = self.__si_connecte("GET", f"/tickets/{numero}")
        return _ou(r, lambda j: conversion.detail(j, lambda b: self.__images.chemin(numero, b)))

    def actions_permises(self, numero: int) -> frozenset:
        if not self.__t.connecte:
            return frozenset()
        r = self.__t.requete("GET", f"/tickets/{numero}")
        return frozenset(conversion.detail(r.valeur).actions) if r.ok else frozenset()

    # ------------------------------------------------ creation
    def creer(self, titre: str, priorite, texte: str = "", images: Iterable[str] = ()) -> Resultat:
        """Meme contrat que le service local : une piece refusee n'annule pas le ticket."""
        r = self.__si_connecte("POST", "/tickets", json={"titre": titre, "priorite": priorite.value, "texte": texte or ""})
        if not r.ok:
            return r
        numero, details = r.valeur["numero"], list(r.valeur["details"])
        for chemin in images:
            ri = self.joindre_image(numero, chemin)
            if not ri.ok:
                details.append(f"image non jointe ({os.path.basename(chemin)}) : {ri.motif}")
        return Resultat.succes(numero, details)

    def ajouter_texte(self, numero: int, texte: str) -> Resultat:
        return _ou(self.__si_connecte("POST", f"/tickets/{numero}/textes", json={"texte": texte}), lambda _: True)

    def joindre_image(self, numero: int, chemin_source: str) -> Resultat:
        """L'image choisie sur cette machine est envoyee au serveur, qui la fait verifier par la fabrique."""
        if not self.__t.connecte:
            return NON_CONNECTE
        nom = os.path.basename(chemin_source)
        if not os.path.isfile(chemin_source):
            return Resultat.echec(f"fichier introuvable : {nom}")
        if os.path.getsize(chemin_source) > LIMITE_IMAGE:
            return Resultat.echec("image de plus de 10 Mo")
        with open(chemin_source, "rb") as f:
            r = self.__t.requete("POST", f"/tickets/{numero}/images", files={"fichier": (nom, f.read())},
                                 delai=DELAI_TELEVERSEMENT)
        return _ou(r, lambda _: True)

    # ------------------------------------------------ actions sur un ticket
    def modifier_titre(self, numero: int, titre: str) -> Resultat:
        return _ou(self.__si_connecte("PATCH", f"/tickets/{numero}", json={"titre": titre}), lambda _: True)

    def commenter(self, numero: int, texte: str) -> Resultat:
        r = self.__si_connecte("POST", f"/tickets/{numero}/commentaires", json={"texte": texte})
        return _ou(r, conversion.commentaire)

    def assigner(self, numero: int, numero_assigne: int) -> Resultat:
        return self.__transition(numero, "assigner", assigne=numero_assigne)

    def soumettre(self, numero: int) -> Resultat:
        return self.__transition(numero, "soumettre")

    def valider(self, numero: int) -> Resultat:
        return self.__transition(numero, "valider")

    def rejeter(self, numero: int, motif: str) -> Resultat:
        return self.__transition(numero, "rejeter", motif=motif)

    def fermer(self, numero: int, motif: str) -> Resultat:
        return self.__transition(numero, "fermer", motif=motif)

    def rouvrir(self, numero: int, motif: str) -> Resultat:
        return self.__transition(numero, "rouvrir", motif=motif)

    def changer_priorite(self, numero: int, priorite) -> Resultat:
        r = self.__si_connecte("PATCH", f"/tickets/{numero}", json={"priorite": priorite.value})
        return _ou(r, lambda _: True)

    def archiver(self, numero: int) -> Resultat:
        return _ou(self.__si_connecte("POST", "/archives", json={"numero": numero}), lambda _: True)
