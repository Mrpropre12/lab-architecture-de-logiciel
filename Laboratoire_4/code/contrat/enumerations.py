"""Valeurs echangees par nom. Memes noms et memes valeurs que les enumerations du modele :
la traduction se fait par la valeur (application/traduction.py)."""
from enum import Enum


class Permission(Enum):
    VIEW = "VIEW"
    COMMENT = "COMMENT"
    EXPORT = "EXPORT"
    CREATE = "CREATE"
    EDIT = "EDIT"
    ATTACH = "ATTACH"
    ASSIGN = "ASSIGN"
    SUBMIT = "SUBMIT"
    VALIDATE = "VALIDATE"
    REJECT = "REJECT"
    CLOSE = "CLOSE"
    REOPEN = "REOPEN"
    SET_PRIORITY = "SET_PRIORITY"
    ARCHIVE = "ARCHIVE"
    VIEW_ALL = "VIEW_ALL"
    MANAGE_USERS = "MANAGE_USERS"


class Priority(Enum):
    BASSE = "BASSE"
    NORMALE = "NORMALE"
    HAUTE = "HAUTE"


class Status(Enum):
    OUVERT = "OUVERT"
    ASSIGNE = "ASSIGNE"
    VALIDATION = "VALIDATION"
    TERMINE = "TERMINE"
    FERME = "FERME"


# Filtres de la liste des tickets (fenetre principale, parametre de requete « filtre »)
MES_TICKETS, TOUS, ASSIGNES_A_MOI = "mes_tickets", "tous", "assignes_a_moi"

# Noms des trois roles du systeme, dans l'ordre d'affichage
ROLES = ("Rapporteur", "Developpeur", "Administrateur")

# Images acceptees dans une description
EXTENSIONS_IMAGES = (".png", ".jpg", ".jpeg", ".gif")
