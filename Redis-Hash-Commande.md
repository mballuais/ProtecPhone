# Stockage de l'agrégat Commande dans Redis (Hash)

## Clé

`protecphone:commande:CMD-42`

## Commande Redis

```
HSET protecphone:commande:CMD-42 commandeId CMD-42 dateCommande 2026-10-07T14:00:00Z clientId CLI-7 clientNom "Marie Dupont" lignes '[{"produitId":"coque-001","nom":"Coque transparente renforcee","couleur":"noir","modele":"iPhone 15","quantite":2,"prixUnitaire":14.99}]' adresseLivraison "12 rue des Lilas, 75000 Paris, France" statut CONFIRMEE total 29.98
```

Vérification :

```
HGETALL protecphone:commande:CMD-42
```

## Passage du JSON au Hash

| Dans le JSON | Dans le Hash | Pourquoi |
|---|---|---|
| commandeId, dateCommande, adresseLivraison, statut, total | un champ chacun | valeurs simples |
| client { clientId, nom } | clientId et clientNom | objet imbriqué mis à plat |
| lignes [ ... ] | un champ lignes | liste stockée en texte JSON |

## Explication

L'agrégat Commande est stocké dans un hash Redis. Chaque attribut simple du JSON devient un champ du hash. L'objet imbriqué `client` est mis à plat en deux champs (`clientId`, `clientNom`), car un hash ne peut pas contenir d'objet. La liste `lignes` est stockée sous forme de texte JSON dans un seul champ.

## Règles de la clé

- **Namespace** : `protecphone:commande:` suivi de l'identifiant de la commande.
- **Ownership** : seul le service Commande est autorisé à écrire cette clé.
- **Lifetime** : pas d'expiration, la clé est mise à jour à chaque événement de la commande.
- **Size limit** : 50 lignes de produits maximum par commande.
