Stockage de l'agrégat Commande dans Redis (Hash)

Clé

`protecphone:demo:order:CMD-42` (configuration Docker Compose)

Commande Redis

```
HSET protecphone:demo:order:CMD-42 commandeId CMD-42 dateCommande 2026-10-07T14:00:00Z client '{"clientId":"CLI-7","nom":"Marie Dupont"}' lignes '[{"produitId":"coque-001","nom":"Coque transparente renforcée","couleur":"noir","modele":"iPhone 15","quantite":2,"prixUnitaire":14.99}]' adresseLivraison "12 rue des Lilas, 75000 Paris, France" statut CONFIRMEE total 29.98
```

Vérification :

```
HGETALL protecphone:demo:order:CMD-42
```

Passage du JSON au Hash

| Dans le JSON | Dans le Hash | Pourquoi |
|---|---|---|
| commandeId, dateCommande, adresseLivraison, statut, total | un champ chacun | valeurs simples |
| client { clientId, nom } | un champ client | objet stocké en texte JSON |
| lignes [ ... ] | un champ lignes | liste stockée en texte JSON |

Explication

L'agrégat Commande est stocké dans un hash Redis. Chaque attribut de premier niveau du JSON devient un champ du hash. L'objet `client` et la liste `lignes` restent imbriqués dans le modèle métier et sont sérialisés en texte JSON dans leurs champs respectifs. `RedisStore.read` les désérialise. Les commandes ci-dessus illustrent le format ; créer et modifier les commandes via l'API pour publier les événements et l'outbox MongoDB. Après la démonstration, CMD-42 est EXPEDIEE.

Règles de la clé

- **Namespace** : `${REDIS_PREFIX}:order:` suivi de l'identifiant ; Compose fixe `REDIS_PREFIX=protecphone:demo`.
- **Ownership** : seul le service Commande est autorisé à écrire cette clé.
- **Lifetime** : pas d'expiration, la clé est mise à jour à chaque événement de la commande.
- **Size limit** : aucune limite de 50 lignes implémentée ; la liste doit être non vide et ses lignes sont validées par le service.

Les lectures via Docker et la projection `orders` MongoDB sont documentées dans [docs/REQUETES-NOSQL.md](docs/REQUETES-NOSQL.md).
