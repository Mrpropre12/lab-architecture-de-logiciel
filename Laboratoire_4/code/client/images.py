"""Cache local des images : l'interface lit une image par son chemin sur le disque.

Les noms donnes par le serveur sont uniques (date, heure, 8 caracteres aleatoires) et un
fichier joint ne change jamais : une image deja telechargee n'est pas redemandee.
"""
import os
import shutil
import tempfile
from typing import Optional

from .transport import Transport


class CacheImages:

    def __init__(self, transport: Transport, dossier: str = None) -> None:
        self.__transport = transport
        self.__dossier = dossier or tempfile.mkdtemp(prefix="tickets_images_")

    @property
    def dossier(self) -> str:
        return self.__dossier

    def chemin(self, numero: int, bloc_json) -> Optional[str]:
        """Fichier local de l'image du ticket numero ; telechargee au premier affichage."""
        nom = os.path.basename(bloc_json["nom"])  # jamais de chemin venant du reseau
        local = os.path.join(self.__dossier, f"{numero}_{nom}")
        if os.path.isfile(local):
            return local
        r = self.__transport.requete("GET", bloc_json["url"], brut=True)
        if not r.ok:
            return None
        with open(local, "wb") as f:
            f.write(r.valeur.content)
        return local

    def vider(self) -> None:
        shutil.rmtree(self.__dossier, ignore_errors=True)
