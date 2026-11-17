# Laboratoire 5 : déploiement avec distribution de charge (6GEI311)

Cours 6GEI311 Architecture des logiciels, UQAC, automne 2026.
Équipe : Christian Kevin Sawadogo et Jeremie Soppewe Arno Tchawo.

Une petite application Flask tourne en deux copies, sur deux machines, derrière un distributeur de charge nginx. L'énoncé est dans [`docs/Enonce_Lab5_6GEI311.pdf`](../docs/Enonce_Lab5_6GEI311.pdf).

## Contenu du dossier

| Fichier | Rôle |
|---|---|
| `app_SCK.py` | Application de Christian (membre A pour ce code) : port 3000 |
| `app_<INITIALES>.py` | Application de Jérémie (membre A pour ce code), à ajouter par lui |
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

## Déroulement : chacun est membre A pour son code

| Manip | Membre A (son code, nginx sur sa machine) | Membre B (lance le code de A sur sa machine) |
|---|---|---|
| 1 | Christian : `app_SCK.py`, port 3000 | Jérémie : copie de `app_SCK.py` avec **son** IP et le port 3001 |
| 2 | Jérémie : `app_<INITIALES>.py`, port 3000 | Christian : copie de ce fichier avec **son** IP et le port 3001 |

Les deux changements du membre B (étape 11 : son IP, port 3001) restent sur sa machine : ils ne se committent pas par-dessus le fichier du membre A.

## Réponses aux questions de la manip

*À compléter pendant la séance, avec ce que vous observez réellement.*

### Étape 6 : l'application est arrêtée, on recharge http://IP_DE_LA_MACHINE:3000/

À compléter.

### Étape 16 : http://IP_MEMBRE_A:8181/, plusieurs rafraîchissements

À compléter.

### Étape 17 : l'application du membre A est arrêtée sur sa machine

a. http://IP_MACHINE_A:3000/ : à compléter.

b. http://IP_MEMBRE_A:8181/ : à compléter.

## Ce que nous avons appris

À compléter après la manip, en quelques phrases.

<!-- Pistes, à retirer avant la remise : le rôle d'un distributeur de charge et d'un proxy inverse ;
     ce qui permet de s'adapter à plus de requêtes ; ce qui se passe quand une copie tombe ;
     pourquoi une application qui garde un état en mémoire (comme le serveur de tickets du labo 4)
     se prête mal à plusieurs copies derrière nginx ; les pièges rencontrés (adresse IP, pare-feu, try_files). -->
