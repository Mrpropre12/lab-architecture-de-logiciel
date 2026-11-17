"""Textes affiches pour les permissions et les actions (francais, accents compris)."""
from application import Permission as P

PERMISSIONS = {
    P.VIEW: "Consulter ses tickets",
    P.COMMENT: "Commenter",
    P.EXPORT: "Exporter en PDF (console seulement dans cette version)",
    P.CREATE: "Créer un ticket",
    P.EDIT: "Modifier le titre de ses tickets",
    P.ATTACH: "Compléter la description de ses tickets",
    P.ASSIGN: "Assigner un ticket",
    P.SUBMIT: "Soumettre son travail à la validation",
    P.VALIDATE: "Valider un travail",
    P.REJECT: "Rejeter un travail",
    P.CLOSE: "Fermer un ticket",
    P.VIEW_ALL: "Voir tous les tickets",
    P.REOPEN: "Rouvrir un ticket",
    P.SET_PRIORITY: "Changer la priorité",
    P.ARCHIVE: "Archiver un ticket",
    P.MANAGE_USERS: "Gérer les comptes et les rôles",
}

# Actions de la fenetre de detail : (permission, libelle du bouton, nom court pour la ligne d'etat)
ACTIONS_TICKET = [
    (P.EDIT, "Modifier le &titre…", "modifier le titre"),
    (P.ATTACH, "Ajouter à la &description…", "ajouter à la description"),
    (P.ASSIGN, "A&ssigner…", "assigner"),
    (P.SUBMIT, "Soumettre à la &validation", "soumettre"),
    (P.VALIDATE, "&Valider", "valider"),
    (P.REJECT, "&Rejeter…", "rejeter"),
    (P.CLOSE, "&Fermer le ticket…", "fermer le ticket"),
    (P.REOPEN, "R&ouvrir…", "rouvrir"),
    (P.SET_PRIORITY, "Changer la &priorité…", "changer la priorité"),
    (P.ARCHIVE, "Arc&hiver…", "archiver"),
]

# Noms des roles du modele (sans accents) tels qu'affiches
ROLES_AFFICHES = {"Rapporteur": "Rapporteur", "Developpeur": "Développeur", "Administrateur": "Administrateur"}


def roles(noms) -> str:
    return ", ".join(ROLES_AFFICHES.get(n, n) for n in noms)
