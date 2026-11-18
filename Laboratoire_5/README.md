# Laboratoire 5 : déploiement avec distribution de charge (6GEI311)

Cours 6GEI311 Architecture des logiciels, UQAC, automne 2026.
Équipe : Christian Kevin Sawadogo et Jeremie Soppewe Arno Tchawo.

Une petite application Flask tourne en deux copies, sur deux machines, derrière un distributeur de charge nginx. L'énoncé est dans [`docs/Enonce_Lab5_6GEI311.pdf`](../docs/Enonce_Lab5_6GEI311.pdf).

## Contenu du dossier

| Fichier | Rôle |
|---|---|
| `app_SCK.py` | Application de Christian (membre A) : port 3000 sur sa machine, port 3001 dans la copie du membre B |
| `nginx.conf` | Bloc `http { ... }` à mettre dans `conf/nginx.conf` de nginx, sur la machine du membre A |
| `requirements.txt` | Flask |

## Préparer la manip (Windows)

1. **Installer Flask**, depuis ce dossier :
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Trouver la bonne adresse IP** avec `ipconfig` : celle de la carte **Wi-Fi**. La carte nommée « Ethernet » en `192.168.56.1` est la carte virtuelle de VirtualBox, que l'autre machine ne peut pas joindre. Sur eduroam, l'adresse change d'une connexion à l'autre : la vérifier le jour même, puis la reporter dans `app_SCK.py` et `nginx.conf`.
3. **Ouvrir le pare-feu.** Windows classe eduroam comme réseau public et y bloque les connexions entrantes. Au premier lancement de Python ou de nginx, accepter l'accès en cochant les réseaux publics, ou, dans un PowerShell en administrateur :
   ```
   New-NetFirewallRule -DisplayName "Lab5 6GEI311" -Direction Inbound -Protocol TCP -LocalPort 3000,3001,8181 -Action Allow
   ```
   et la retirer après la séance : `Remove-NetFirewallRule -DisplayName "Lab5 6GEI311"`.
4. **Vérifier que les deux machines se voient** : `Test-NetConnection IP_DE_L_AUTRE -Port 3000` (ou 3001). Si le réseau isole les appareils entre eux, ce qui arrive sur les Wi-Fi d'université, brancher les deux ordinateurs sur le partage de connexion d'un même téléphone et refaire l'étape 2.
5. **nginx sous Windows**, depuis son dossier (voir https://nginx.org/en/docs/windows.html) :
   ```
   start nginx            démarrer
   nginx -s reload        relire conf/nginx.conf après une modification
   nginx -s stop          arrêter
   tasklist /fi "imagename eq nginx.exe"    vérifier qu'il tourne
   ```

**Correction de la configuration de l'énoncé.** Le bloc `location /` fourni contient `try_files $uri $uri/ =404;` en plus de `proxy_pass`. `try_files` s'exécute avant `proxy_pass` : nginx cherche d'abord un fichier dans son propre dossier `html` et répond lui-même (sa page d'accueil ou une erreur 404), sans jamais transmettre la requête aux applications. Notre `nginx.conf` retire cette ligne.

## Rôles

| Membre A (son code, nginx sur sa machine) | Membre B (lance le code de A sur sa machine) |
|---|---|
| Christian : `app_SCK.py`, port 3000 | Jérémie : copie de `app_SCK.py` avec **son** IP et le port 3001 |

Les deux changements du membre B (étape 11 : son IP, port 3001) restent sur sa machine : ils ne se committent pas par-dessus le fichier du membre A.

## Journal de la manip (Christian membre A, Jérémie membre B), 17 et 18 novembre 2026

| Étape | Ce qui a été fait | Résultat |
|---|---|---|
| 1 | Flask installé dans l'environnement virtuel du dépôt | Flask 3.1.3, Python 3.13.5 |
| 2 et 3 | `app_SCK.py` avec les initiales SCK et l'adresse Wi-Fi | `172.19.129.254` (réseau eduroam) |
| 4 et 5 | Application lancée ; http://172.19.129.254:3000/ ouverte dans le navigateur | « Hello, World! From SCK: 172.19.129.254 » |
| 6 | Application arrêtée, page rechargée | voir la réponse plus bas |
| 7 | Application relancée | la page revient |
| 8 | Code poussé sur GitHub | `Laboratoire_5/app_SCK.py` disponible pour le membre B |
| 10 | nginx 1.31.8 pour Windows décompressé dans `C:\Users\kevin\nginx-1.31.8` et lancé | http://localhost/ affiche « Welcome to nginx! » |
| 9, 11 à 13 | Jérémie (membre B) récupère `app_SCK.py` par GitHub, y met son adresse et le port 3001, et la lance | page vérifiée par Jérémie dans son navigateur, sur le port 3001 |
| Vérification | `Test-NetConnection 172.19.138.206 -Port 3001` depuis la machine de Christian, sur eduroam | échec : `DestinationHostUnreachable`, adresse matérielle introuvable (`Get-NetNeighbor` : `Unreachable`) ; eduroam isole les appareils entre eux |
| Contournement | Les deux ordinateurs passent sur le partage de connexion d'un même iPhone ; adresses mises à jour dans `app_SCK.py` et dans la copie de Jérémie | Christian `172.20.10.4`, Jérémie `172.20.10.3` ; `Test-NetConnection 172.20.10.3 -Port 3001` réussit |
| 14 et 15 | Bloc `http` de `C:\Users\kevin\nginx-1.31.8\conf\nginx.conf` remplacé par `nginx.conf` (`172.20.10.4:3000` et `172.20.10.3:3001`), `nginx -t`, `nginx -s reload` | configuration valide, rechargée sans arrêter nginx |
| 16 et 17 | Observations | voir les réponses plus bas |

## Réponses aux questions de la manip

Observations de la manip (Christian membre A, Jérémie membre B) : l'étape 6 le 17 novembre 2026 sur eduroam, les étapes 16 et 17 le 18 novembre, les deux machines sur le partage de connexion d'un téléphone.

### Étape 6 : l'application est arrêtée, on recharge http://IP_DE_LA_MACHINE:3000/

La page n'est plus accessible : le navigateur affiche « 172.19.129.254 a refusé de se connecter » (`ERR_CONNECTION_REFUSED`). La machine est bien jointe, mais plus aucun programme n'écoute sur le port 3000, donc le système refuse la connexion. La page n'existe que tant que l'application tourne : sans serveur en marche, il n'y a rien pour répondre à la requête. Une fois l'application relancée (étape 7), la page revient.

### Étape 16 : http://IP_MEMBRE_A:8181/, plusieurs rafraîchissements

À chaque rafraîchissement de http://172.20.10.4:8181/, l'affichage change : la page affiche tantôt l'adresse de Christian (`172.20.10.4`), tantôt celle de Jérémie (`172.20.10.3`). On interroge pourtant toujours la même adresse, celle de nginx sur la machine du membre A. nginx ne produit pas la page lui-même : il transmet chaque requête à l'une des deux applications du groupe `upstream labcluster`, à tour de rôle (répartition circulaire, ou *round robin*, son comportement par défaut). Le client ne sait pas quelle machine lui répond ; seule l'adresse écrite dans la page, ajoutée pour l'expérience, permet de le voir.

### Étape 17 : l'application du membre A est arrêtée sur sa machine

a. http://172.20.10.4:3000/ : aucune réponse. Comme à l'étape 6, plus aucun programme n'écoute sur le port 3000 de la machine A : l'application n'est plus accessible directement.

b. http://172.20.10.4:8181/ : l'application reste accessible ; on observe la page de Jérémie (`172.20.10.3`). nginx tourne toujours sur la machine A. Quand il ne parvient pas à joindre l'application de Christian, il transmet la requête à l'autre serveur du groupe, puis écarte pendant un moment le serveur en panne. Pour l'utilisateur, le service continue : c'est la tolérance aux pannes qu'apporte un distributeur de charge, tant qu'il reste au moins une copie en marche.

## Ce que nous avons appris

- **Une application web n'existe que tant que son serveur tourne.** Arrêter l'application rend la page inaccessible immédiatement (étape 6) : avec une seule copie, la moindre panne coupe le service.
- **Choisir la bonne adresse IP.** Un ordinateur a plusieurs cartes réseau. Notre première version utilisait `192.168.56.1`, l'adresse de la carte virtuelle de VirtualBox, que l'autre machine ne peut pas joindre ; la bonne est celle de la carte Wi-Fi. Sur eduroam, cette adresse est attribuée à chaque connexion et peut changer d'une séance à l'autre.
- **Le réseau lui-même peut empêcher le déploiement.** Sur eduroam, nos deux machines avaient des adresses du même sous-réseau, mais ne pouvaient pas se joindre : le réseau sans fil de l'université isole les appareils entre eux. Le diagnostic l'a montré (`DestinationHostUnreachable`, adresse matérielle introuvable) ; ni le code ni le pare-feu n'étaient en cause. Un réseau à nous, le partage de connexion d'un téléphone, a réglé le problème.
- **Le pare-feu fait partie du déploiement.** Une page qui s'affiche sur sa propre machine ne prouve pas qu'elle est joignable depuis une autre : Windows classe eduroam comme réseau public et bloque les connexions entrantes tant qu'on ne les autorise pas.
- **Lire la configuration avant de l'appliquer.** Dans le bloc `location /` de l'énoncé, `try_files` passe avant `proxy_pass` : nginx cherche d'abord un fichier dans son propre dossier et répond lui-même, au lieu de transmettre la requête aux applications. Notre `nginx.conf` retire cette ligne, et la répartition a fonctionné.
- **Un distributeur de charge répartit les requêtes et masque les pannes.** Derrière nginx, les clients n'utilisent qu'une seule adresse, et nginx alterne entre les copies de l'application (étape 16). Pour absorber plus de requêtes, il suffit d'ajouter une copie dans le groupe `upstream`, sans rien changer côté client. Quand une copie tombe, le service reste disponible par l'autre (étape 17), alors qu'avec une seule copie la page disparaissait (étape 6).
- **Les copies doivent être interchangeables.** Ici, elles ne diffèrent que par l'adresse affichée, ajoutée pour l'expérience. Une application qui garde un état en mémoire, comme le serveur de tickets du labo 4 (données et comptes connectés), se prêterait mal à plusieurs copies : chacune aurait ses propres données, et une requête pourrait tomber sur une copie qui ne connaît pas l'utilisateur. Il faudrait alors partager l'état (base de données commune) ou renvoyer un client toujours vers la même copie.
- **nginx lui-même devient un point unique de défaillance.** Si la machine A ou nginx s'arrête, plus rien n'est accessible par le port 8181, même si les applications tournent encore. Dans un vrai système, on doublerait aussi le distributeur.
