# Résultats réels de validation

Validation effectuée le **29 octobre 2026** sous Windows / PowerShell avec
Docker Desktop, moteur Linux/WSL2. Redis 7.4.2, MongoDB 8.0.16, Java 21,
Spring Boot 3.5.7. Aucun Redis/MongoDB simulé.

Ports de validation : 28081 (Produit), 28082 (Commandes), 28083 (SAV), 6380 (Redis).
Ils évitent les ports déjà utilisés par d'autres projets, qui n'ont pas été arrêtés.
MongoDB est accessible uniquement sur le réseau interne Docker.
Java et Maven n'étant pas installés dans le PATH hôte, compilation dans Docker.
Maven ne trouve pas de tests Java : les 18 tests et les pannes sont exécutés par
la suite Python contre les conteneurs réels, séparément de la compilation Maven.

## Exécution reproductible

```powershell
$env:PRODUCT_PORT='28081'
$env:ORDERS_PORT='28082'
$env:SAV_PORT='28083'
$env:REDIS_BIND_PORT='6380'
python scripts/validate.py --no-build
```

Omettre `--no-build` lors de la première exécution ou après modification Java.
`scripts/validate.py` conserve stdout/stderr réels dans `validation/integration.log`
et le code de sortie, les dates UTC et le commit de base dans `validation/result.json`.
Le code attendu et observé pour la suite terminée est **0**.

## Couverture vérifiée

| Vérification | Résultat | Preuve |
|---|---|---|
| Construction Java 21 / Maven verify | Réussie dans Docker | validation/build.log, Dockerfile |
| Santé Redis, MongoDB et trois services | Tous disponibles | Attentes Compose `--wait` |
| HGETALL, HGET, HEXISTS et types Hash | Réussis | test_01 et scénario demo |
| Trois agrégats et deux répliques MongoDB | Identiques aux lectures Redis | demo, test_15, mongo_verify |
| Publication/consommation des événements | Réussies, files vidées | test_02, métriques et journal |
| Produit → Commandes | Création, prix, stock et mise à jour complète | test_03, test_07, test_08 |
| Commandes → Produit | Stocks 78 / 49 / 27 après commandes | test_04 et demo |
| Commandes → SAV | Commande et changements de statut copiés | test_05, test_10, test_11 |
| SAV → Commandes | Statut reçu par événement | test_06 |
| Doublon de OrderCreated | Stock inchangé | test_09 |
| Annulation et restitution unique | Stock initial restauré | test_10 |
| Retour de commande | Stock restauré | test_11 |
| Commande invalide / création en double | 400 / 409, pas d'événement parasite | test_12, test_13 |
| Plusieurs lignes et variantes | Stocks [8,17], total 56 | test_14 |
| Doublons d'événements de répliques | Aucun nouveau traitement ni événement | test_16 |
| Rejeu du lot MongoDB | Même document au même identifiant | test_17 |
| Accès MongoDB limité au rôle | 404 sur les collections d'un autre rôle | test_18 |
| Commandes arrêté puis relancé | File accumulée, puis consommée | offline-publish / offline-verify |
| Message en cours pendant redémarrage Redis | Repris, stock 98, rejeu sans effet | stage-inflight / recovered |
| Redémarrage MongoDB | Documents persistants et lisibles | mongo-verify |
| MongoDB arrêté pendant une mutation | Outbox conservée, Redis disponible | mongo-offline |
| Redémarrage Produit pendant cette panne | Convergence prix 14.49 dans les deux bases | mongo-recovered |
| Arrêt brutal SIGKILL Produit | Données et idempotence conservées | recovered après kill |
| Comptage après tous les rejeux | 6/5/2/6/5, sans doublon | mongosh à la fin de run.py test |
| Reset limité au projet | Témoins hors namespace conservés puis retirés | reset Redis et mongo_reset |

La suite unittest contient **18 tests réussis**. Les scénarios de redémarrage,
de panne et les vérifications de reset sont des étapes supplémentaires de l'orchestrateur,
pas des tests unittest comptés artificiellement.

Les tests ajoutent coque-test, CMD-TEST et CMD-RECOVERY ; les comptes après tests
diffèrent donc volontairement de ceux de la démonstration initiale.

## Requêtes et reproductibilité de présentation

Après validation, la démonstration est rechargée deux fois pour vérifier le reset
et l'absence de doublons. La trace est conservée dans `validation/reproductibilite.log`.
Les **15 commandes** de `REQUETES-NOSQL.md` sont rejouées par `scripts/query_demo.py`
et leurs sorties conservées dans `validation/requetes.log`.
Après demo : 5 products, 3 orders, 2 sav_tickets, 5 product_replicas, 3 order_replicas ;
14 événements, stocks 78/49/27/40/100 et CMD-42 EXPEDIEE dans les deux bases.

Le PDF est contrôlé par extraction de texte et rendu des sept pages : aucune page
vide, aucun texte tronqué observé. Le README, les huit JSON et ListEvents sont
comparés à origin/main et conservés. L'archive ZIP est contrôlée par CRC et manifeste SHA-256.

## Incidents détectés et corrigés

Le premier démarrage a rencontré des ports hôte occupés. Utilisation des variables
Compose pour les API/Redis et suppression de la publication hôte MongoDB inutile.

Une première suite avait réussi les 18 tests mais échoué lors d'une lecture MongoDB
immédiatement après la panne : le healthcheck MongoDB était disponible avant la
reconnexion de tous les clients Java. `mongo_verify` attend maintenant, avec délai
borné, une lecture correcte de chaque document. La tentative initiale est conservée
dans `validation/reprise-initiale.log`. La suite complète corrigée a terminé avec succès.

## Limites de couverture

Pas de test de charge, de panne disque, de suppression de volumes, de haute
disponibilité, de déploiement cloud ou de plusieurs instances par rôle. Pas de
validation sur un autre OS hôte dans cette mission ; les services et les tests
s'exécutent dans des conteneurs Linux et l'orchestration utilise la bibliothèque
standard Python. La démonstration n'est pas une application de production sécurisée.
La compensation métier de survente concurrente reste hors périmètre.
La publication GitHub est vérifiée séparément ; aucun accès Moodle n'a permis
une remise effective dans cette session.
