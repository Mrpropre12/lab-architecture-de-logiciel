"""Exporte la definition OpenAPI de l'API dans docs/openapi.yaml (pour la remise du labo 4).

Usage, depuis le dossier code :  python outils/openapi.py
La definition est generee par FastAPI a partir des routes et des schemas : elle ne peut
pas diverger du code. Le serveur la publie aussi en direct : /openapi.json et /docs.
"""
import os
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(ICI)
sys.path.insert(0, CODE)
os.environ.setdefault("TICKETS_UPLOAD_DIR", tempfile.mkdtemp(prefix="televersements_"))

import yaml  # noqa: E402  (pip install pyyaml, outil de remise seulement)

from gestion_tickets.acteurs import UserRegistry  # noqa: E402
from gestion_tickets.ticket import TicketRegistry  # noqa: E402
from serveur import creer_api  # noqa: E402

UserRegistry.PBKDF2_ITERATIONS = 1_000  # aucun compte reel : seule la forme de l'API compte ici


def main() -> int:
    users = UserRegistry("Admin", "admin@uqac.ca", "admin-openapi")
    app = creer_api(users, TicketRegistry(users), os.environ["TICKETS_UPLOAD_DIR"], web=False)
    sortie = os.path.join(CODE, "docs", "openapi.yaml")
    with open(sortie, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(app.openapi(), f, sort_keys=False, allow_unicode=True, width=110)
    print(f"Definition OpenAPI ecrite dans {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
