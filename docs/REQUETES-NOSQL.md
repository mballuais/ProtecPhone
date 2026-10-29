# Requêtes exécutables Redis et MongoDB

Exécuter à la racine après `python scripts/run.py demo --no-build`.
Commandes compatibles PowerShell, sans redis-cli ni mongosh installés sur l'hôte.
Résultats attendus pour le scénario demo, pas pour l'état modifié par les tests.
`python scripts/query_demo.py` rejoue toutes ces lectures et conserve leur sortie.

## Redis

### Agrégat Produit (HGETALL)

```sh
docker compose exec -T redis redis-cli HGETALL protecphone:demo:product:coque-001
```

Attendu : produitId=coque-001, nom=Coque transparente renforcée,
compatibilite=[iPhone 15], variantes contenant couleur=noir, prix=14.99, stock=78.
L'ordre des champs d'un Hash n'est pas contractuel.

### Lire le statut (HGET)

```sh
docker compose exec -T redis redis-cli HGET protecphone:demo:order:CMD-42 statut
```

Attendu : `EXPEDIEE`.

### Vérifier l'identifiant (HEXISTS)

```sh
docker compose exec -T redis redis-cli HEXISTS protecphone:demo:order:CMD-42 commandeId
```

Attendu : `1`.

### Lire la réplique Commande

```sh
docker compose exec -T redis redis-cli HGETALL protecphone:demo:replica:order:CMD-42
```

Attendu : CMD-42, total 29.98, client CLI-7 imbriqué en JSON, statut EXPEDIEE,
deux coques noires iPhone 15, aucune adresse de livraison.

### Journal d'événements (LRANGE)

```sh
docker compose exec -T redis redis-cli LRANGE protecphone:demo:events 0 0
```

Attendu : une enveloppe ProductCreated émise par product pour coque-001.
eventId et occurredAt changent à chaque rechargement. `0 -1` lit tout le journal.

### Taille du journal (LLEN)

```sh
docker compose exec -T redis redis-cli LLEN protecphone:demo:events
```

Attendu : `14` (5 ProductCreated, 3 OrderCreated, 3 StockChanged,
2 AfterSalesStatusChanged, 1 OrderStatusChanged).

### File consommée et projection terminée

```sh
docker compose exec -T redis redis-cli LLEN protecphone:demo:queue:orders
docker compose exec -T redis redis-cli LLEN protecphone:demo:mongo:processing:sav
```

Attendu : `0` pour chacune après convergence.

## MongoDB — base protecphone

Chaque filtre inclut `_namespace` pour isoler les données de démonstration.
La projection `{_id:0,_namespace:0}` masque seulement les métadonnées techniques.

### Tous les produits (find)

```sh
docker compose exec -T mongodb mongosh protecphone --quiet --eval "db.products.find({_namespace:'protecphone:demo'},{_id:0,_namespace:0}).sort({produitId:1}).toArray()"
```

Attendu : cinq produits, stocks principaux 78, 49, 27, 40, 100.

### Une commande (findOne)

```sh
docker compose exec -T mongodb mongosh protecphone --quiet --eval "db.orders.findOne({_namespace:'protecphone:demo',commandeId:'CMD-42'},{_id:0,_namespace:0})"
```

Attendu : commande de Marie Dupont (CLI-7), total 29.98, statut EXPEDIEE,
client et lignes imbriqués et adresse de livraison conservée.

### Filtre sur le statut

```sh
docker compose exec -T mongodb mongosh protecphone --quiet --eval "db.orders.find({_namespace:'protecphone:demo',statut:'CONFIRMEE'},{commandeId:1,_id:0}).sort({commandeId:1}).toArray()"
```

Attendu : CMD-43 et CMD-44.

### Champ imbriqué du client

```sh
docker compose exec -T mongodb mongosh protecphone --quiet --eval "db.orders.find({_namespace:'protecphone:demo','client.clientId':'CLI-7'},{commandeId:1,total:1,_id:0}).toArray()"
```

Attendu : CMD-42, total 29.98.

### Champ imbriqué d'un tableau

```sh
docker compose exec -T mongodb mongosh protecphone --quiet --eval "db.products.find({_namespace:'protecphone:demo','variantes.stock':78},{produitId:1,_id:0}).toArray()"
```

Attendu : coque-001.

### Copie Produit détenue par Commandes

```sh
docker compose exec -T mongodb mongosh protecphone --quiet --eval "db.product_replicas.findOne({_namespace:'protecphone:demo',produitId:'coque-001'},{_id:0,_namespace:0})"
```

Attendu : variante noire à 14.99 et stock 78, identique au Produit courant.

### Copie Commande détenue par SAV

```sh
docker compose exec -T mongodb mongosh protecphone --quiet --eval "db.order_replicas.findOne({_namespace:'protecphone:demo',commandeId:'CMD-42'},{_id:0,_namespace:0})"
```

Attendu : statut EXPEDIEE, total 29.98, client CLI-7 et lignes conservés,
adresseLivraison absente. Cette modification provient de OrderStatusChanged.
