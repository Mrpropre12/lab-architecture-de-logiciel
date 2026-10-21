"""Faire entrer un fichier choisi par l'utilisateur dans le dossier de televersement.

Le modele n'accepte que des fichiers situes dans son dossier de televersement
(confinement du labo 2). L'interface, elle, laisse choisir une image n'importe
ou, et laisse taper du texte. Cette classe fait le pont, sans contourner aucune
regle : elle copie l'image (ou ecrit le texte dans un .txt) sous un nom unique,
puis passe par ContentFactory, qui verifie tout comme au labo 2. Si la fabrique
refuse, la copie est supprimee.
"""
import os
import secrets
import shutil
from datetime import datetime

from gestion_tickets.ticket import ContentFactory, ImageFileContent, TextFileContent

from .resultat import CaptureMotif, Resultat

EXTENSIONS_IMAGES = (".png", ".jpg", ".jpeg", ".gif")


class ImportFichiers:

    def __init__(self, dossier: str) -> None:
        """dossier : le dossier de televersement du modele (injecte par le point d'entree)."""
        self.__dossier = dossier

    @property
    def dossier(self) -> str:
        return self.__dossier

    def __nom_unique(self, extension: str) -> str:
        """Date, heure et 8 caracteres aleatoires, comme les noms des PDF du labo 2."""
        return f"{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(4)}{extension}"

    def __passer_par_la_fabrique(self, nom: str, type_attendu) -> Resultat:
        with CaptureMotif() as capture:
            contenu = ContentFactory.from_path(nom)
        if contenu is None or not isinstance(contenu, type_attendu):
            self.supprimer(nom)
            return Resultat.echec(capture.motif_ou("fichier refuse par la fabrique"))
        return Resultat.succes(contenu)

    def importer_image(self, chemin_source: str) -> Resultat:
        """Copie l'image choisie, puis la fait verifier par la fabrique. valeur : le contenu."""
        extension = os.path.splitext(chemin_source)[1].lower()
        if extension not in EXTENSIONS_IMAGES:
            return Resultat.echec("seules les images .png, .jpg et .gif sont acceptees")
        if not os.path.isfile(chemin_source):
            return Resultat.echec(f"fichier introuvable : {os.path.basename(chemin_source)}")
        os.makedirs(self.__dossier, exist_ok=True)
        nom = self.__nom_unique(extension)
        try:
            shutil.copyfile(chemin_source, os.path.join(self.__dossier, nom))
        except OSError as e:
            return Resultat.echec(f"copie impossible : {e.strerror or e}")
        return self.__passer_par_la_fabrique(nom, ImageFileContent)

    def enregistrer_texte(self, texte: str) -> Resultat:
        """Ecrit le texte tape dans un .txt, puis le fait verifier par la fabrique."""
        if not isinstance(texte, str) or not texte.strip():
            return Resultat.echec("le texte est vide")
        os.makedirs(self.__dossier, exist_ok=True)
        nom = self.__nom_unique(".txt")
        try:
            with open(os.path.join(self.__dossier, nom), "w", encoding="utf-8", newline="\n") as f:
                f.write(texte.replace("\r\n", "\n").strip() + "\n")
        except OSError as e:
            return Resultat.echec(f"ecriture impossible : {e.strerror or e}")
        return self.__passer_par_la_fabrique(nom, TextFileContent)

    def supprimer(self, nom_ou_chemin: str) -> None:
        """Retire un fichier importe qui n'a finalement pas ete joint (reste dans le dossier)."""
        chemin = os.path.join(self.__dossier, os.path.basename(nom_ou_chemin))
        try:
            os.remove(chemin)
        except OSError:
            pass
