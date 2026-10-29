# ProtecPhone — Plateforme e-commerce de coques de téléphone

Projet **NoSQL / Architecture Microservices** — EFREI Paris, Master 1, encadré par M. Charroux.

**Groupe :** Ilyesse El Adaoui, Touria Serrakh, Matteo Balluais, Sheyma Daoud
**Technologies :** Java (Spring Boot, Maven) • Redis • MongoDB • Docker • Python

## 📝 Présentation du projet

ProtecPhone modélise la vente de coques de smartphones et le suivi après-vente, découpés en trois microservices indépendants.

Le périmètre implémenté comprend :

- les API de catalogue (produits, prix et stock par couleur) ;
- les commandes avec calcul du total et changements de statut ;
- les réservations et restitutions de stock ;
- les tickets SAV (réclamations, retours, échanges de messages).

Les clients de démonstration sont fictifs. Aucun frontend, paiement ou moteur de recommandation n'est nécessaire au scénario présenté.

## 🏗️ Architecture des microservices

Les trois services sont des conteneurs indépendants construits depuis le même artefact Maven. La variable `SERVICE_ROLE` sélectionne les routes et le consommateur d'événements. Chaque donnée est possédée logiquement par un seul service ; les autres n'en conservent que les copies nécessaires.

| Service | Responsabilité | Données possédées | Données copiées |
|---------|----------------|-------------------|-----------------|
| **Produit** | Catalogue, prix et stock par couleur | Produits ; registre d'allocation | — |
| **Commandes** | Validation des lignes, total et statut | Commandes | Copie des Produits |
| **SAV** | Tickets et échanges de messages | Tickets | Copie des Commandes (sans adresse) |

```
   Produit            Commandes             SAV
catalogue/stocks   commandes/copie Produit  tickets/copie Commande
        \                |                 /
         Redis : Hashes + Lists (événements, idempotence, reprise, outbox)
                         |
              Projecteurs Java (FIFO / replaceOne)
                         |
         MongoDB : documents métier et répliques
```

## 📦 Agrégats métier et répliques

Les schémas de référence sont `Aggregat-Produit.json`, `Aggregat-Commande.json`, `Aggregat-SAV.json` et les deux fichiers `Replica-*.json`. Les enveloppes `Commande-*.json` restent acceptées par `POST /commands`.

- **Produit** : modèles compatibles et variantes ; le prix et le stock dépendent de la couleur.
- **Commande** : identité/date, client (imbriqué, sans collection Client distincte), lignes, adresse, statut et total. Chaque ligne conserve nom, modèle, couleur, quantité et prix unitaire au moment de l'achat.
- **Ticket SAV** : `ticketId`, `commandeId`, `dateCreation`, motif, statut et messages (auteur, texte, date ISO-8601).

| Réplique | Contenu conservé | Alimentation |
|----------|------------------|--------------|
| Produit dans Commandes | Produit complet et variantes | Événements Produit |
| Commande dans SAV | Client, lignes, date, total, statut ; sans adresse | Événements Commande |

La copie Produit permet à Commandes de valider une commande sans appel HTTP direct à Produit. La copie Commande permet au SAV de vérifier l'existence d'une commande sans dépendre de sa disponibilité. Il s'agit de **cohérence éventuelle**.

## 🗄️ Rôle des bases de données

| Base | Rôle |
|------|------|
| **Redis** | Hashes opérationnels (agrégats et copies locales) et files d'événements (Lists) : journal, attente, reprise, déduplication et outbox persistante. |
| **MongoDB** | Documents métier (produits, commandes, tickets) et répliques locales, interrogeables par filtres documentaires (client, variantes, statut) sans jointure. |

### Redis

Tous les suffixes sont précédés de `protecphone:demo:` dans Compose.

| Structure | Exemple de suffixe | Usage |
|-----------|--------------------|-------|
| Hash | `product:coque-001`, `order:CMD-42`, `sav:SAV-9` | Agrégats opérationnels |
| Hash | `replica:product:coque-001`, `replica:order:CMD-42` | Copies locales |
| List | `events`, `queue:orders`, `processing:orders` | Journal, attente et reprise |
| Hash | `processed:orders`, `metrics:orders` | Déduplication et compteur |
| List | `mongo:queue:orders`, `mongo:processing:orders` | Outbox documentaire |

La persistance AOF est activée (`appendfsync always`) sur le volume `redis-data`. Les écritures métier, les événements et l'ajout à l'outbox sont regroupés dans un même script Lua. `LMOVE` déplace atomiquement un message de `queue` vers `processing` ; un même `eventId` n'a jamais de second effet.

### MongoDB

La base s'appelle `protecphone`.

| Collection | Propriétaire |
|------------|--------------|
| `products` | Produit |
| `orders` | Commandes |
| `sav_tickets` | SAV |
| `product_replicas` | Commandes |
| `order_replicas` | SAV |

Les collections `stock_allocations` et `sav_status_replicas` conservent des registres auxiliaires. Chaque document porte `_id` (égal à la clé Redis complète) et `_namespace` (`protecphone:demo`). Le volume `mongo-data` assure la persistance.

Exemple de requête dans `mongosh` :

```js
db.orders.findOne({ _namespace: 'protecphone:demo', commandeId: 'CMD-42' })
```

## 🔄 Synchronisation et reprise sur panne

Redis est le point de validation opérationnel : chaque écriture ajoute aussi les snapshots à projeter dans une **outbox**, au même commit. Un worker Java indépendant par rôle met ensuite MongoDB à jour (`replaceOne` par `_id` avec `upsert`), puis acquitte le lot. Rejouer un lot est donc idempotent.

| Incident | Comportement |
|----------|--------------|
| MongoDB arrêté | Redis accepte l'écriture et garde l'outbox ; reprise automatique |
| Arrêt après écriture Mongo, avant acquittement | Même remplacement rejoué, sans doublon |
| Service indisponible | Événements conservés dans sa queue ; consommation au retour |
| Message invalide | Conservé dans `dead` avec l'erreur |

La réponse HTTP confirme Redis et l'outbox, pas l'achèvement côté MongoDB.

## ⚙️ Prérequis

- **Docker Desktop** démarré
- **Python 3.10+**

Java et Maven sont fournis par Docker.

## 🚀 Commandes principales

Lancer l'infrastructure (construction des images, démarrage en arrière-plan) :

```bash
docker compose up --build -d
```

Exécuter le scénario de démonstration (5 produits, 3 commandes, 2 tickets) :

```bash
python scripts/run.py demo
```

Valider le système (tests d'intégration et scénarios de panne/reprise) :

```bash
python scripts/validate.py
```

Les ports hôte par défaut sont `8081` / `8082` / `8083` (services) et `6379` (Redis), configurables par variables. MongoDB reste sur le réseau Docker.

> Les tests modifient volontairement le jeu de données : relancer `python scripts/run.py demo` avant une présentation.

## ✅ Validation

La validation utilise de vrais conteneurs Redis, MongoDB et trois services Spring Boot, sans base simulée : 18 tests d'intégration réussis, puis tous les scénarios de panne et de reprise terminés avec le code 0. Les traces sont conservées dans `docs/validation/`.

## 📚 Documentation

- `docs/REQUETES-NOSQL.md` : commandes Redis et mongosh avec résultats réels
- `docs/TESTS.md` : résultats, configuration et limites de couverture
- `docs/validation/` : journaux d'intégration et `result.json`
- `ProtecPhone-Rapport-NoSQL.pdf` : rapport complet du projet

## ⚠️ Limites connues

Pas de haute disponibilité, pas de saga de compensation des surventes concurrentes, pas de rotation automatique des journaux, pas de contrôle d'accès par service au niveau des bases, et la perte des volumes n'est pas couverte. La validation locale ne constitue pas une certification de charge ni de sécurité de production.
