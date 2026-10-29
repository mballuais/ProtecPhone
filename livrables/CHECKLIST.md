# Checklist du rendu

| Exigence du professeur | Statut | Preuve | Emplacement |
|---|---|---|---|
| Au moins deux services programmés | Validé : trois services Java | Conteneurs product, orders, sav ; rôles API | docker-compose.yml, src/main/java/fr/protecphone/ |
| Deux bases NoSQL réellement utilisées | Validé : Redis et MongoDB | Lectures et écritures réelles, tests comparatifs | RedisStore.java, MongoProjection.java, docs/validation/ |
| Un agrégat propre par service | Validé : Produit, Commande, SAV | Trois collections et trois familles de Hashes | Aggregat-*.json, docs/ARCHITECTURE.md |
| Un service conserve une réplique d'un autre | Validé : deux répliques | Produit dans Commandes, Commande dans SAV | Replica-*.json, test_15 |
| Mise à jour des répliques par événements | Validé | Création, prix, stock, annulation et statut | Business.receive, RedisStore, scripts/checks.py |
| Mini-rapport PDF | Généré et contrôlé, 7 pages | PDF et source éditable | rapport/ProtecPhone-Rapport-NoSQL.pdf et .md |
| Dépôt Git contenant l'application | Préparé pour publication | Code, Compose, scripts, preuves | https://github.com/mballuais/ProtecPhone |
| Dépôt sur Moodle avant le 15/11/2026 | Intervention étudiante requise | Archive et procédure prêtes ; aucune remise annoncée | livrables/REMISE-MOODLE.md |

| Finalisation complémentaire | Statut / preuve |
|---|---|
| Démonstration en une commande | `python scripts/run.py demo` |
| Données fictives reproductibles | 5 produits, 3 clients, 3 commandes, 2 tickets ; reset isolé |
| Stock et statuts cohérents | Vérifications API, Redis et MongoDB après convergence |
| Idempotence | Événements dédupliqués ; snapshots MongoDB remplacés au même _id |
| Reprise et persistance | Tests de redémarrage des deux bases et des services |
| Résultats réels | 18 tests + scénarios de panne ; docs/TESTS.md et logs |
| Bases interrogeables | 15 commandes Docker ; docs/REQUETES-NOSQL.md |
| Schéma d'architecture | Mermaid dans docs/ARCHITECTURE.md ; dessin dans le PDF |
| README du groupe et exemples métier | Conservés intégralement |
| Archive sans dépendances ni secrets | ZIP, manifeste SHA-256 et contrôle CRC |
| Noms des membres | Champ à compléter par le groupe dans la source du rapport |

Ne pas confondre la validation technique et la remise administrative. Le statut
de publication effectif est à vérifier sur GitHub ; Moodle exige un téléversement
et une confirmation par l'étudiant.
