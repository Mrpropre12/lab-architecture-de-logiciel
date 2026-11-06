"""Transport HTTP du client : une requete, un Resultat du contrat.

Toute reponse d'erreur de l'API a la forme {motif, details, cause} : elle redevient le
Resultat que le service aurait rendu en local. Une panne du reseau devient un Resultat
de cause INJOIGNABLE, affiche dans le bandeau habituel de l'interface.
"""
from typing import Optional

import httpx

from contrat import Cause, Profil, Resultat

PREFIXE = "/api/v1"
DELAI = 10.0           # secondes par requete
DELAI_REVEIL = 90.0    # un service Render gratuit endormi met environ une minute a repartir
DELAI_TELEVERSEMENT = 30.0

NON_CONNECTE = Resultat.echec("aucun compte connecte", cause=Cause.NON_CONNECTE)


class Transport:
    """Connexion a l'API : client httpx, jeton du compte connecte, profil connu."""

    def __init__(self, url: str = None, http: httpx.Client = None) -> None:
        """url : adresse du serveur (https://...onrender.com) ; http : client deja construit (tests)."""
        if http is None:
            http = httpx.Client(base_url=url.rstrip("/"), timeout=DELAI, follow_redirects=True,
                                headers={"User-Agent": "gestionnaire-tickets-6gei311"})
        self.__http = http
        self.__jeton: Optional[str] = None
        self.profil: Optional[Profil] = None  # dernier profil recu (None : aucun compte connecte)

    @property
    def url(self) -> str:
        return str(self.__http.base_url)

    @property
    def connecte(self) -> bool:
        return self.__jeton is not None

    def ouvrir(self, jeton: str, profil: Profil) -> None:
        self.__jeton, self.profil = jeton, profil

    def fermer(self) -> None:
        """Se deconnecter : oublier le jeton (il expire seul cote serveur)."""
        self.__jeton, self.profil = None, None

    def fin(self) -> None:
        self.__http.close()

    # ------------------------------------------------ requetes
    def requete(self, methode: str, chemin: str, delai: float = DELAI, brut: bool = False, **kwargs) -> Resultat:
        """valeur : le JSON de la reponse (ou la reponse httpx si brut). Refus : motif, details et cause de l'API."""
        entetes = {"Authorization": f"Bearer {self.__jeton}"} if self.__jeton else {}
        try:
            r = self.__http.request(methode, chemin if chemin.startswith(PREFIXE) else PREFIXE + chemin,
                                    headers=entetes, timeout=delai, **kwargs)
        except httpx.TimeoutException:
            return Resultat.echec(f"le serveur ne repond pas (delai de {delai:g} s depasse)", cause=Cause.INJOIGNABLE)
        except httpx.TransportError as e:
            return Resultat.echec(f"serveur injoignable ({self.url}) : {e.__class__.__name__}", cause=Cause.INJOIGNABLE)
        if r.is_success:
            if brut:
                return Resultat.succes(r)
            return Resultat.succes(r.json() if r.content else None)
        return self.__refus(r)

    def __refus(self, r: httpx.Response) -> Resultat:
        try:
            corps = r.json()
            cause = Cause(corps["cause"])
            motif = corps["motif"]
            details = corps.get("details", [])
        except (ValueError, KeyError, TypeError):
            # pas une erreur de l'API (page d'attente de Render, mandataire...) : le service n'est pas joignable
            return Resultat.echec(f"reponse inattendue du serveur (HTTP {r.status_code})", cause=Cause.INJOIGNABLE)
        if r.status_code == 401 and self.__jeton:
            self.fermer()  # jeton expire, compte desactive ou serveur redemarre : il faut se reconnecter
        return Resultat.echec(motif, details, cause)

    def reveiller(self) -> Resultat:
        """GET /sante avec un long delai : reveille un service endormi avant la connexion."""
        return self.requete("GET", "/sante", delai=DELAI_REVEIL)
