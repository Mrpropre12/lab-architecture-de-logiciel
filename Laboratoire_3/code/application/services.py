"""Services d'application : un appel de methode par geste de l'utilisateur.

Chaque methode passe le compte connecte comme acteur, appelle l'API publique du
modele et renvoie un Resultat (OK, ou REFUSE avec le motif ecrit par le modele).
Aucune regle metier ici : le modele decide de tout.
"""
import os
from typing import Callable, Iterable, Optional

from gestion_tickets.acteurs import AdminRole, DeveloperRole, Permission, ReporterRole, User
from gestion_tickets.consultation import DescriptionVisitor
from gestion_tickets.ticket import Priority, Status, Ticket

from .fichiers import ImportFichiers
from .resultat import CaptureMotif, Resultat
from .session import Session
from .vues import CompteVue, DetailTicket, LigneTicket, Profil

_NON_CONNECTE = Resultat.echec("aucun compte connecte")
ROLES = {"Rapporteur": ReporterRole, "Developpeur": DeveloperRole, "Administrateur": AdminRole}

# Filtres de la liste des tickets (fenetre principale)
MES_TICKETS, TOUS, ASSIGNES_A_MOI = "mes_tickets", "tous", "assignes_a_moi"


def _noms_des_roles(u: User) -> tuple:
    ordre = list(ROLES)
    return tuple(sorted((r.name() for r in u.get_roles()), key=lambda n: ordre.index(n) if n in ordre else 99))


def _ligne(t: Ticket) -> LigneTicket:
    assigne = t.get_assignee()
    return LigneTicket(t.ticket_id, t.title, t.get_status(), t.priority, t.get_author().name,
                       assigne.name if assigne else None, t.update_date, t.is_archived())


class ServiceComptes:

    def __init__(self, session: Session) -> None:
        self.__session = session

    # ------------------------------------------------ connexion
    def connecter(self, courriel: str, mot_de_passe: str) -> Resultat:
        with CaptureMotif() as capture:
            compte = self.__session.users.authenticate(courriel, mot_de_passe)
        if compte is None:
            return Resultat.echec(capture.motif_ou("courriel ou mot de passe incorrect"))
        self.__session.ouvrir(compte)
        return Resultat.succes(self.profil().valeur)

    def deconnecter(self) -> Resultat:
        self.__session.fermer()
        return Resultat.succes()

    def inscrire(self, nom: str, courriel: str, mot_de_passe: str, confirmation: str) -> Resultat:
        """Inscription libre (role Rapporteur). La confirmation evite une faute de frappe."""
        if mot_de_passe != confirmation:
            return Resultat.echec("les deux mots de passe ne sont pas identiques")
        with CaptureMotif() as capture:
            compte = self.__session.users.register(nom, courriel, mot_de_passe)
        if compte is None:
            return Resultat.echec(capture.motif_ou("inscription refusee"))
        return Resultat.succes(compte.name)

    # ------------------------------------------------ lecture
    def profil(self) -> Resultat:
        u = self.__session.connecte
        if u is None:
            return _NON_CONNECTE
        permissions = tuple(p for p in Permission if u.can_globally(p))
        return Resultat.succes(Profil(u.user_id, u.name, _noms_des_roles(u), permissions))

    def lister(self) -> Resultat:
        """Tous les comptes (MANAGE_USERS)."""
        acteur = self.__session.connecte
        if acteur is None:
            return _NON_CONNECTE
        with CaptureMotif() as capture:
            comptes = self.__session.users.find_all(acteur)
        if not comptes:
            return Resultat.echec(capture.motif_ou("liste des comptes refusee"))
        return Resultat.succes([CompteVue(u.user_id, u.name, _noms_des_roles(u), u.active) for u in comptes])

    # ------------------------------------------------ gestion (MANAGE_USERS)
    def __gerer(self, numero: int, appel: Callable) -> Resultat:
        acteur = self.__session.connecte
        if acteur is None:
            return _NON_CONNECTE
        with CaptureMotif() as capture:
            cible = self.__session.users.find_by_id(acteur, numero)
            ok = cible is not None and appel(acteur, cible)
        if not ok:
            return Resultat.echec(capture.motif_ou(f"compte {numero} introuvable"))
        details = ()
        if not acteur.active:  # l'acteur s'est desactive lui-meme
            self.__session.fermer()
            details = ("votre compte est desactive : vous avez ete deconnecte",)
        return Resultat.succes(cible.name, details)

    def __role(self, nom_role: str):
        type_role = ROLES.get(nom_role)
        return type_role() if type_role else None

    def attribuer_role(self, numero: int, nom_role: str) -> Resultat:
        role = self.__role(nom_role)
        if role is None:
            return Resultat.echec(f"role inconnu : {nom_role}")
        return self.__gerer(numero, lambda a, c: self.__session.users.grant_role(a, c, role))

    def retirer_role(self, numero: int, nom_role: str) -> Resultat:
        role = self.__role(nom_role)
        if role is None:
            return Resultat.echec(f"role inconnu : {nom_role}")
        return self.__gerer(numero, lambda a, c: self.__session.users.revoke_role(a, c, role))

    def desactiver(self, numero: int) -> Resultat:
        return self.__gerer(numero, self.__session.users.deactivate)

    def reactiver(self, numero: int) -> Resultat:
        return self.__gerer(numero, self.__session.users.reactivate)


class ServiceTickets:

    def __init__(self, session: Session, importateur: ImportFichiers) -> None:
        self.__session = session
        self.__import = importateur

    # ------------------------------------------------ outils
    def __acteur(self) -> Optional[User]:
        return self.__session.connecte

    def __agir(self, numero: int, appel: Callable[[Ticket, User], object], valeur=None) -> Resultat:
        """Retrouve le ticket visible, appelle le modele, traduit sa reponse en Resultat."""
        acteur = self.__acteur()
        if acteur is None:
            return _NON_CONNECTE
        with CaptureMotif() as capture:
            ticket = self.__session.tickets.find_by_id(acteur, numero)
            reponse = appel(ticket, acteur) if ticket is not None else None
        if ticket is None:
            return Resultat.echec(capture.motif_ou(f"ticket {numero} introuvable"))
        if not reponse:
            return Resultat.echec(capture.motif_ou("action refusee"))
        return Resultat.succes(valeur if valeur is not None else reponse)

    # ------------------------------------------------ listes
    def lister(self, filtre: str = MES_TICKETS, statut: Optional[Status] = None,
               priorite: Optional[Priority] = None) -> Resultat:
        """Tickets actifs selon le filtre, puis, au besoin, selon le statut et la priorite.
        Chaque critere est une recherche du modele : la visibilite reste la sienne."""
        acteur = self.__acteur()
        if acteur is None:
            return _NON_CONNECTE
        reg = self.__session.tickets
        with CaptureMotif() as capture:
            if filtre == TOUS:
                base = reg.find_all(acteur)
            elif filtre == ASSIGNES_A_MOI:
                base = reg.find_by_assignee(acteur, acteur)
            elif filtre == MES_TICKETS:
                base = reg.find_by_author(acteur, acteur) + reg.find_by_assignee(acteur, acteur)
            else:
                return Resultat.echec(f"filtre inconnu : {filtre}")
            if filtre == TOUS and not base and not acteur.can_globally(Permission.VIEW_ALL):
                return Resultat.echec(capture.motif_ou("liste refusee"))
            if statut is not None:
                gardes = {t.ticket_id for t in reg.find_by_status(acteur, statut)}
                base = [t for t in base if t.ticket_id in gardes]
            if priorite is not None:
                gardes = {t.ticket_id for t in reg.find_by_priority(acteur, priorite)}
                base = [t for t in base if t.ticket_id in gardes]
        uniques = {t.ticket_id: t for t in base}
        return Resultat.succes([_ligne(t) for _, t in sorted(uniques.items())])

    def archives(self) -> Resultat:
        acteur = self.__acteur()
        if acteur is None:
            return _NON_CONNECTE
        return Resultat.succes([_ligne(t) for t in self.__session.tickets.find_archived(acteur)])

    def assignables(self) -> Resultat:
        """Comptes actifs qui peuvent etre assignes (droit SUBMIT).

        Le modele rend les comptes actifs visibles a tout acteur actif (find_by_id) :
        on les parcourt par numero, sans exiger MANAGE_USERS."""
        acteur = self.__acteur()
        if acteur is None:
            return _NON_CONNECTE
        users = self.__session.users
        with CaptureMotif():
            comptes = [users.find_by_id(acteur, n) for n in range(1, users.next_id)]
        return Resultat.succes([CompteVue(u.user_id, u.name, _noms_des_roles(u), u.active)
                                for u in comptes if u is not None and u.can_globally(Permission.SUBMIT)])

    # ------------------------------------------------ detail
    def detail(self, numero: int) -> Resultat:
        """Blocs a afficher et actions permises maintenant (pour griser les boutons)."""
        visiteur = DescriptionVisitor()
        r = self.__agir(numero, lambda t, a: t.consult(a, visiteur) and t)
        if not r.ok:
            return r
        ticket = r.valeur
        return Resultat.succes(DetailTicket(numero, visiteur.blocks(),
                                            ticket.allowed_actions(self.__acteur()), visiteur.result()))

    def actions_permises(self, numero: int) -> frozenset:
        """Permissions exercables maintenant sur ce ticket (vide si invisible ou non connecte)."""
        acteur = self.__acteur()
        if acteur is None:
            return frozenset()
        with CaptureMotif():
            ticket = self.__session.tickets.find_by_id(acteur, numero)
        return ticket.allowed_actions(acteur) if ticket is not None else frozenset()

    # ------------------------------------------------ creation
    def creer(self, titre: str, priorite: Priority, texte: str = "", images: Iterable[str] = ()) -> Resultat:
        """Cree le ticket, puis joint le texte et les images. Une piece refusee
        n'annule pas le ticket : elle est signalee dans details. valeur : le numero."""
        acteur = self.__acteur()
        if acteur is None:
            return _NON_CONNECTE
        with CaptureMotif() as capture:
            ticket = self.__session.tickets.create(acteur, titre, priorite)
        if ticket is None:
            return Resultat.echec(capture.motif_ou("creation refusee"))
        details = []
        if texte and texte.strip():
            r = self.ajouter_texte(ticket.ticket_id, texte)
            if not r.ok:
                details.append(f"texte non joint : {r.motif}")
        for chemin in images:
            r = self.joindre_image(ticket.ticket_id, chemin)
            if not r.ok:
                details.append(f"image non jointe ({os.path.basename(chemin)}) : {r.motif}")
        return Resultat.succes(ticket.ticket_id, details)

    def __joindre(self, numero: int, import_resultat: Resultat) -> Resultat:
        if not import_resultat.ok:
            return import_resultat
        contenu = import_resultat.valeur
        r = self.__agir(numero, lambda t, a: t.add_content(a, contenu))
        if not r.ok:
            self.__import.supprimer(contenu.path)
        return r

    def ajouter_texte(self, numero: int, texte: str) -> Resultat:
        """Le texte tape devient un .txt verifie par la fabrique, puis est joint."""
        if self.__acteur() is None:
            return _NON_CONNECTE
        return self.__joindre(numero, self.__import.enregistrer_texte(texte))

    def joindre_image(self, numero: int, chemin_source: str) -> Resultat:
        """L'image choisie est copiee dans le dossier de televersement, verifiee, puis jointe."""
        if self.__acteur() is None:
            return _NON_CONNECTE
        return self.__joindre(numero, self.__import.importer_image(chemin_source))

    # ------------------------------------------------ actions sur un ticket
    def modifier_titre(self, numero: int, titre: str) -> Resultat:
        return self.__agir(numero, lambda t, a: t.edit(a, titre))

    def commenter(self, numero: int, texte: str) -> Resultat:
        return self.__agir(numero, lambda t, a: t.add_comment(a, texte))

    def assigner(self, numero: int, numero_assigne: int) -> Resultat:
        def appel(t, a):
            assigne = self.__session.users.find_by_id(a, numero_assigne)
            return t.assign(a, assigne)
        return self.__agir(numero, appel)

    def soumettre(self, numero: int) -> Resultat:
        return self.__agir(numero, lambda t, a: t.submit(a))

    def valider(self, numero: int) -> Resultat:
        return self.__agir(numero, lambda t, a: t.validate(a))

    def rejeter(self, numero: int, motif: str) -> Resultat:
        return self.__agir(numero, lambda t, a: t.reject(a, motif))

    def fermer(self, numero: int, motif: str) -> Resultat:
        return self.__agir(numero, lambda t, a: t.close(a, motif))

    def rouvrir(self, numero: int, motif: str) -> Resultat:
        return self.__agir(numero, lambda t, a: t.reopen(a, motif))

    def changer_priorite(self, numero: int, priorite: Priority) -> Resultat:
        return self.__agir(numero, lambda t, a: t.set_priority(a, priorite))

    def archiver(self, numero: int) -> Resultat:
        return self.__agir(numero, lambda t, a: self.__session.tickets.archive(a, t.ticket_id))
