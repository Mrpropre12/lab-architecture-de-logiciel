"""JSON de l'API -> types du contrat (l'inverse de serveur/schemas.py).

Les dates arrivent avec le fuseau du serveur (UTC sur Render) ; l'interface les affiche
a l'heure locale de la machine qui affiche.
"""
from datetime import datetime
from typing import Optional

import contrat
from contrat import Permission, Priority, Status


def date(texte: Optional[str]) -> Optional[datetime]:
    if texte is None:
        return None
    d = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    return d.astimezone().replace(tzinfo=None) if d.tzinfo else d


def profil(j) -> contrat.Profil:
    return contrat.Profil(j["numero"], j["nom"], tuple(j["roles"]), tuple(Permission(p) for p in j["permissions"]))


def compte(j) -> contrat.CompteVue:
    return contrat.CompteVue(j["numero"], j["nom"], tuple(j["roles"]), j["actif"])


def ligne(j) -> contrat.LigneTicket:
    return contrat.LigneTicket(j["numero"], j["titre"], Status(j["statut"]), Priority(j["priorite"]), j["auteur"],
                               j["assigne"], date(j["modifie_le"]), j["archive"])


def commentaire(j) -> contrat.BlocCommentaire:
    return contrat.BlocCommentaire(j["numero"], j["auteur"], date(j["publie_le"]), j["texte"])


def bloc(j, chemin_image=None):
    """chemin_image(bloc_json) : fichier local de l'image (cache), ou None si le telechargement a echoue."""
    nature = j["type"]
    if nature == "ticket":
        return contrat.BlocTicket(j["numero"], j["titre"], j["statut"], j["priorite"], j["auteur"], j["assigne"],
                                  date(j["cree_le"]), date(j["modifie_le"]), date(j["archive_le"]))
    if nature == "texte":
        return contrat.BlocTexte(j["nom"], j["texte"])
    if nature == "image":
        chemin = chemin_image(j) if chemin_image else None
        if chemin is None:  # image non telechargee : affichee comme illisible, avec son nom
            return contrat.BlocImage(j["nom"], "", None, None)
        return contrat.BlocImage(j["nom"], chemin, j["largeur"], j["hauteur"])
    if nature == "video":
        return contrat.BlocVideo(j["nom"])
    return commentaire(j)


def detail(j, chemin_image=None) -> contrat.DetailTicket:
    return contrat.DetailTicket(j["numero"], tuple(bloc(b, chemin_image) for b in j["blocs"]),
                                frozenset(Permission(p) for p in j["actions"]), j["texte"])
