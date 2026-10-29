# Audit initial — 29 octobre 2026

Le dépôt local était sur `f52c52d`. Après `git fetch origin main`, intégration
fast-forward de `33ed96474adf85c8f2c046309da081b75fffb0ba`, dernière version
distante disponible lors de l'audit. Les quatre modifications locales préexistantes
(`docker-compose.yml`, `Api.java`, `Business.java`, `RedisStore.java`) ont été conservées.
Elles modifiaient notamment les ports hôte : 8081/8082/8083 et 6379.

Lecture de tous les fichiers source, des huit exemples JSON, de `ListEvents`,
des scripts Python, de Compose, du Dockerfile, du POM, du README et des documents.
Aucun `AGENTS.md` trouvé dans le dépôt. Le README et les exemples JSON sont conservés.

| Élément | Constat avant modification | Action |
|---|---|---|
| Produit / Commandes / SAV | Trois processus Spring Boot sélectionnés par rôle | Réutilisés |
| Redis | Hashes, Lists, journal, Lua de commit, allocation du stock | Conservés, ajout outbox au commit |
| Événements | Fan-out, reprise LMOVE, déduplication eventId, rejet dead | Conservés |
| Tests | 14 tests réels Redis/API et scénarios de redémarrage | Étendus à MongoDB |
| Données | 5 produits, 3 clients, 3 commandes, 2 SAV déjà prévus | Réutilisés |
| MongoDB | Absent du POM, du code et de Compose | Ajout effectif et interrogeable |
| Documentation Commande | Clé `commande:` et client aplati différents du code | Correction documentaire |
| Rapport / remise | Absents | Rapport éditable, PDF, archive et procédure |

Java et Maven absents du PATH hôte. Docker Desktop était arrêté ; son démarrage
a rendu possible la compilation Java 21/Maven et les validations dans Docker.
Les résultats actuels sont dans `docs/TESTS.md`, sans déduire les résultats de
cette mission des validations Redis antérieures du 26 octobre.

Limites préexistantes préservées : une instance par rôle, disponibilité du stock
vérifiée sur une réplique asynchrone, sans saga de compensation en cas de concurrence.
Les fonctionnalités envisagées par le README (frontend, recommandations, suppression)
ne sont pas toutes implémentées ; le rapport décrit uniquement les API effectives.
