# Démarrer et présenter ProtecPhone

Prérequis : Docker Desktop démarré en mode conteneurs Linux, Compose v2,
Python 3.10+ sur l'hôte. Java 21 et Maven sont fournis par Docker. Aucun package
Python n'est nécessaire à la démonstration ou aux tests. La première construction
nécessite Internet pour les images et dépendances Maven.

Depuis la racine du dépôt, dans PowerShell, cmd ou un terminal POSIX :

```sh
docker compose up --build -d
docker compose ps
python scripts/run.py demo
```

La dernière commande suffit à construire, démarrer, charger et vérifier l'ensemble.
Après une construction, `python scripts/run.py demo --no-build` réutilise l'image.

| Composant | Adresse locale |
|---|---|
| Produit | http://localhost:8081 |
| Commandes | http://localhost:8082 |
| SAV | http://localhost:8083 |
| Redis | localhost:6379 |
| MongoDB | réseau Docker `mongodb:27017`, base `protecphone` |

Les cinq conteneurs ont un healthcheck. Les ports hôte reprennent les modifications
locales existantes du groupe ; s'ils sont occupés, changer uniquement le port à
gauche du `:` dans Compose. Les scripts s'exécutent sur le réseau interne Docker.
Toutes les publications hôte sont limitées à 127.0.0.1.

Si les ports du groupe sont déjà occupés, les variables d'environnement permettent
de les adapter sans changer le code. Exemple PowerShell utilisé pour la validation :

```powershell
$env:PRODUCT_PORT='28081'
$env:ORDERS_PORT='28082'
$env:SAV_PORT='28083'
$env:REDIS_BIND_PORT='6380'
python scripts/validate.py
```

MongoDB n'occupe aucun port hôte ; les requêtes passent par `docker compose exec`.
Avec ces variables, remplacer 8081/8082/8083 par 28081/28082/28083 dans les lectures HTTP.

## Scénario de présentation

Le script arrête les écrivains, supprime uniquement les clés `protecphone:demo:*`
et les documents MongoDB marqués `_namespace: protecphone:demo` dans les collections
connues. Il ne fait ni FLUSHDB, ni dropDatabase, ni suppression de volume.
Cet espace est réservé aux données fictives et réinitialisé à chaque lancement.
Les autres namespaces sont préservés. Les identifiants sont recréés proprement,
donc un second lancement ne crée aucun doublon.

1. Créer les cinq produits et vérifier les copies automatiques dans Commandes.
2. Créer CMD-42/43/44 pour CLI-7/8/9 (Marie Dupont, Lucas Martin, Sarah Bernard).
3. Vérifier stocks 78, 49, 27 et les copies Commande dans SAV.
4. Créer SAV-9 (coque fissurée) et SAV-10 (couleur incorrecte).
5. Expédier CMD-42 et vérifier le statut EXPEDIEE dans la copie SAV.
6. Attendre toutes les files puis comparer chaque document MongoDB à Redis.
7. Exécuter des lectures mongosh et compter 5 produits, 3 commandes, 2 tickets,
   5 copies Produit et 3 copies Commande (18 documents métier, hors registres).

Stocks finaux après `demo` : coque-001=78, coque-002=49, coque-003=27,
coque-004=40, coque-005=100. Total CMD-42=29.98, CMD-43=19.99, CMD-44=74.97.
Le nom historique « Coque transparente renforcée » pour coque-001 est conservé ;
la variante achetée est noire. Les cinq variantes principales, prix et stocks
initiaux correspondent au scénario demandé.

Lectures depuis PowerShell :

```powershell
Invoke-RestMethod http://localhost:8081/products/coque-001
Invoke-RestMethod http://localhost:8081/documents/products/coque-001
Invoke-RestMethod http://localhost:8082/documents/product_replicas/coque-001
Invoke-RestMethod http://localhost:8083/documents/order_replicas/CMD-42
```

`/documents/{collection}/{id}` lit MongoDB et contrôle le rôle ; les autres routes
historiques lisent les Hashes Redis. Toutes les routes métier et les enveloppes
de `Commande-*.json` restent disponibles (voir `REDIS-DEMO.md`).

## Validation et arrêt

```sh
python scripts/validate.py
python scripts/run.py demo --no-build
docker compose down
```

`validate.py` lance `run.py test` et sauvegarde log et code de sortie dans
`docs/validation/`. Les tests changent prix, statuts, stocks et ajoutent des
identifiants techniques ; relancer demo restaure les données de présentation.
`down` conserve les volumes ; ne pas utiliser `down -v` pour vérifier la persistance.
Un échec lève une erreur et retourne un code non nul. Les reprises sont bornées
par des attentes de test ; les workers applicatifs retentent les pannes transitoires.

Le rapport se reconstruit avec Python et ReportLab (dépendance uniquement éditoriale) :

```sh
python -m pip install -r rapport/requirements.txt
python scripts/build_report.py
python scripts/package_delivery.py
```

Voir `REQUETES-NOSQL.md`, `ARCHITECTURE.md`, `TESTS.md` et `livrables/REMISE-MOODLE.md`.
