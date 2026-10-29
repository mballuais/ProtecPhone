# Démonstration Redis ProtecPhone

> Mise à jour du 29 octobre 2026 : MongoDB complète maintenant cette démonstration.
> Les commandes ci-dessous restent utilisables. Voir [DEMARRAGE.md](DEMARRAGE.md),
> [ARCHITECTURE.md](ARCHITECTURE.md), [REQUETES-NOSQL.md](REQUETES-NOSQL.md)
> et [TESTS.md](TESTS.md) pour la version finale et ses résultats actuels.

Java 21, Spring Boot, Redis Hashes et Redis Lists. Les trois services sont des
processus et conteneurs indépendants, construits à partir du même projet Maven.
`SERVICE_ROLE` sélectionne les routes métier et le consommateur du processus.
Les agrégats, commandes, répliques JSON, `ListEvents` et `README.md` restent inchangés.

## Démarrer

Prérequis : Docker avec Compose v2. Python 3.10+ sert uniquement à orchestrer la
démonstration et les tests ; Java et Maven sont fournis par l'image de compilation.

```sh
docker compose up --build -d
docker compose ps
```

| Composant | Adresse locale |
|---|---|
| Produit | http://localhost:8081 |
| Commandes | http://localhost:8082 |
| SAV | http://localhost:8083 |
| Redis | localhost:6379 |

La santé de chaque API est accessible sur `/actuator/health`. Les ports sont
personnalisables via `PRODUCT_PORT`, `ORDERS_PORT`, `SAV_PORT`, `REDIS_BIND_PORT`.
Redis utilise un volume persistant et AOF avec `appendfsync always`.

## Démonstration complète, reproductible

Depuis la racine du dépôt :

```sh
python scripts/run.py demo
```

Le script démarre Redis et MongoDB, arrête les trois services avant la remise à zéro,
supprime uniquement les clés `protecphone:demo:*` et les documents de ce namespace, reconstruit et démarre les
services, puis crée les données via les API métier. Il attend chaque projection
avec un délai maximal et échoue avec un code non nul et un diagnostic si une
vérification échoue. Il ne crée jamais directement les répliques.

Le jeu de données comporte cinq produits, les trois clients CLI-7/8/9, les
commandes CMD-42/43/44 et les tickets SAV-9/10. Les clients restent imbriqués dans
les commandes, conformément à l'agrégat existant.

Résultats attendus : stocks `78, 49, 27, 40, 100`, répliques Produit synchronisées,
trois répliques Commande dans SAV, deux tickets et CMD-42 à `EXPEDIEE` dans SAV.
Les Hashes, événements, répliques et résultats sont affichés ou vérifiés.

Pour réutiliser une image déjà construite :

```sh
python scripts/run.py demo --no-build
```

Le préfixe par défaut du code Java est `protecphone`. Compose utilise
`protecphone:demo` pour isoler la démonstration. La remise à zéro refuse tout
autre préfixe et n'utilise ni `FLUSHDB` ni `FLUSHALL`. Ne pas stocker de données
à conserver sous ce préfixe réservé à la démonstration.

## Utiliser les commandes JSON existantes

Sur une instance vide, dans l'ordre (attendre la réplique avant l'étape suivante) :

```sh
curl -X POST http://localhost:8081/commands -H "Content-Type: application/json" --data-binary @Commande-CreateProduct.json
curl http://localhost:8082/replicas/products/coque-001
curl -X POST http://localhost:8082/commands -H "Content-Type: application/json" --data-binary @Commande-CreateOrder.json
curl http://localhost:8083/replicas/orders/CMD-42
curl -X POST http://localhost:8083/commands -H "Content-Type: application/json" --data-binary @Commande-CreateSAVTicket.json
```

Sous PowerShell, utiliser `curl.exe` pour ces exemples. Après le script de
démonstration, ces identifiants existent déjà : une recréation renvoie `409`.

Les API acceptent aussi directement le contenu de `payload` :

| Service | Méthode et route | Effet |
|---|---|---|
| Produit | `POST /products` | Créer le Hash et publier ProductCreated |
| Produit | `GET /products/{id}` | Consulter le produit |
| Produit | `PUT /products/{id}` | Remplacer les champs métier, publier ProductUpdated |
| Produit | `PATCH /products/{id}/variants` | Recevoir `{ "couleur": "noir", "prix": 15.99, "stock": 80 }` ; prix et stock facultatifs séparément |
| Commandes | `GET /replicas/products/{id}` | Consulter la copie locale du produit |
| Commandes | `POST /orders` | Créer une commande et publier OrderCreated |
| Commandes | `GET /orders/{id}` | Consulter la commande |
| Commandes | `PATCH /orders/{id}/status` | Recevoir `{ "statut": "EXPEDIEE" }` |
| SAV | `GET /replicas/orders/{id}` | Consulter la copie locale de la commande |
| SAV | `POST /tickets` | Créer un ticket lié à une commande répliquée |
| SAV | `GET /tickets/{id}` | Consulter le ticket |
| SAV | `PATCH /tickets/{id}/status` | Modifier le statut du ticket |
| Commandes | `GET /orders/{id}/sav/{ticketId}` | Consulter le statut SAV reçu par événement |

Statuts Commande : CONFIRMEE → EXPEDIEE → LIVREE → RETOURNEE, ou
CONFIRMEE → ANNULEE. L'annulation et le retour remettent les quantités en stock.
Le total est calculé et les quantités, prix, modèles et variantes sont vérifiés.

## Voir les Hashes et les Lists

```sh
docker compose exec redis redis-cli HGETALL protecphone:demo:product:coque-001
docker compose exec redis redis-cli HGET protecphone:demo:product:coque-001 variantes
docker compose exec redis redis-cli HEXISTS protecphone:demo:order:CMD-42 commandeId
docker compose exec redis redis-cli HGETALL protecphone:demo:replica:product:coque-001
docker compose exec redis redis-cli HGETALL protecphone:demo:replica:order:CMD-42
docker compose exec redis redis-cli HGETALL protecphone:demo:sav:SAV-9
docker compose exec redis redis-cli LRANGE protecphone:demo:events 0 -1
docker compose exec redis redis-cli LLEN protecphone:demo:queue:product
docker compose exec redis redis-cli LRANGE protecphone:demo:processing:product 0 -1
docker compose exec redis redis-cli HGETALL protecphone:demo:metrics:product
docker compose logs --tail 40 product orders sav
```

Les Hashes contiennent un champ par propriété métier ; objets et tableaux sont
des chaînes JSON. Les nombres sont des valeurs textuelles Redis converties à la
lecture. `HSET`, `HGETALL`, `HGET` et `HEXISTS` servent au stockage/contrôle ;
`HINCRBY` compte les événements traités. Les stocks par variante restent dans le
tableau `variantes`, sans aplatir ni modifier le modèle métier existant.

## Événements et reprise

Chaque enveloppe contient `eventId` (UUID), `type`, `source`, `occurredAt`, `data`.
Les noms avec espaces de `ListEvents` sont normalisés sans espaces dans le code.

| Événement | Émetteur | Destinataires | Données |
|---|---|---|---|
| ProductCreated / ProductUpdated | product | orders | Produit complet |
| PriceChanged / StockChanged | product | orders | Produit complet, variantes actualisées |
| OrderCreated | orders | product, sav | Commande complète, client et lignes imbriqués |
| OrderCancelled | orders | product, sav | Commande annulée complète, lignes à restituer |
| OrderStatusChanged | orders | sav | commandeId, statut |
| ProductReturned | orders | product | Commande et lignes retournées |
| AfterSalesStatusChanged | sav | orders | ticketId, commandeId, statut |

Le service émetteur distribue une copie dans chaque file concernée par `RPUSH` ;
aucun routeur supplémentaire n'est nécessaire. `LMOVE LEFT RIGHT` déplace
atomiquement le prochain message de `queue:{service}` vers `processing:{service}`.
Le consommateur reprend d'abord le message en cours, y compris après redémarrage.

Un script Lua regroupe les écritures des Hashes, les événements suivants, le
marquage `processed:{service}` et l'acquittement `LREM`. Un rejeu du même eventId
est acquitté sans réappliquer les effets. Un registre `product:allocation:{id}`
évite également une seconde réservation/restitution d'une même commande avec
un nouvel identifiant d'événement. Une erreur Redis transitoire conserve le
message dans `processing` et déclenche une nouvelle tentative. Un événement
invalide est conservé dans `dead:{service}` avec son erreur et sa date.

Le journal `events` conserve les événements même lorsque les files sont vides.
Les compteurs `metrics:{service}` et les registres d'idempotence sont également
persistés dans Redis.

Cette démonstration utilise un seul Redis et une seule instance par rôle : ne
pas multiplier les consommateurs d'un rôle, car ils partagent la liste de reprise.
Les répliques sont cohérentes après traitement asynchrone, pas immédiatement à
la réponse HTTP. Une commande valide sa disponibilité sur la réplique ; en cas
de concurrence dépassant le stock réel, Produit refuse l'événement dans sa file
`dead`, sans stock négatif. La résolution métier de cette commande est hors du
scénario pédagogique. Le journal et les registres sont conservés jusqu'au reset.

Références : [file fiable LMOVE](https://redis.io/docs/latest/commands/lmove/),
[transactions de file avec Lua et Lettuce](https://redis.io/docs/latest/develop/use-cases/job-queue/java-lettuce/).

## Exécuter les tests réels

```sh
python scripts/run.py test
```

Les tests utilisent les trois API, un vrai Redis et un vrai MongoDB Docker, sans simulation.
La suite Python vérifie les Hashes, publication/consommation, les quatre sens
de communication, les projections, les prix, les stocks, les doublons,
annulations/retours, deux variantes d'un même produit et les entrées invalides.

L'orchestrateur arrête ensuite réellement Commandes pour vérifier l'accumulation
et la reprise de sa file. Il arrête Produit et place un événement réclamé dans
`processing` pour simuler une interruption avant traitement. Il redémarre Redis
pour vérifier la persistance, puis Produit pour vérifier la reprise et rejoue le
message. Enfin, il tue Produit avec SIGKILL, le redémarre et vérifie encore le
stock et l'idempotence. Chaque étape est vérifiée ; un échec arrête le script.

Les tests modifient leurs données fictives (annulations, retours, prix).
Relancer `python scripts/run.py demo --no-build` pour retrouver la présentation
initiale. `docker compose down` arrête les composants sans supprimer le volume.

Validation exécutée le 26 octobre 2026 : compilation Docker réussie,
`Ran 14 tests ... OK`, puis réussite des vérifications d'indisponibilité,
de reprise du message en cours, de persistance Redis et d'arrêt brutal.
Le contenu versionné de `README.md` a été vérifié inchangé. Les nouveaux commits
README publiés par le groupe pendant le développement ont été intégrés avant
la publication, sans modification de leur contenu par cet ajout Redis.
