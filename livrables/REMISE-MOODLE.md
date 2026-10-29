# Remise ProtecPhone — 15 novembre 2026

Dépôt : https://github.com/mballuais/ProtecPhone

Fichiers à téléverser sur Moodle selon les champs proposés par le professeur :

1. `rapport/ProtecPhone-Rapport-NoSQL.pdf` (mini-rapport).
2. `livrables/ProtecPhone-Rendu-NoSQL.zip` (application, sources du rapport,
   documentation et preuves de validation) si une archive du projet est demandée.
3. Le lien GitHub ci-dessus dans le champ prévu ou le commentaire de remise.

L'archive contient un dossier `ProtecPhone/`. Extraire puis ouvrir un terminal
dans ce dossier. Avec Docker Desktop démarré et Python 3.10+ :

```sh
docker compose up --build -d
python scripts/run.py demo
```

Pour reproduire les tests : `python scripts/validate.py`.
La première exécution télécharge des images et dépendances. Aucun compte cloud,
abonnement, Java ou Maven sur l'hôte n'est nécessaire. Les ports occupés peuvent
être adaptés par les variables détaillées dans `docs/DEMARRAGE.md`.
Redis et MongoDB persistent dans des volumes locaux. Le scénario recharge
uniquement les données fictives de l'espace réservé `protecphone:demo`.

Avant téléversement :

- Régénérer le PDF avec `python scripts/build_report.py`, puis l'archive avec
  `python scripts/package_delivery.py` (ReportLab requis pour le PDF uniquement).
- Vérifier la version GitHub publiée, ouvrir le PDF et vérifier l'archive.
- Consulter `CHECKLIST.md` et `docs/TESTS.md`.
- Vérifier que Moodle affiche la remise et sa confirmation avant la date limite.

L'archive exclut `.git`, `.env`, `target`, les dépendances et caches ; aucun mot de
passe n'est requis par cette configuration locale. `MANIFEST-SHA256.json` permet
de vérifier chaque fichier et le fichier `.zip.sha256` l'archive complète.
Le README du groupe est conservé intégralement.

Aucun accès Moodle n'est connecté dans cette session. Le dépôt Moodle n'a pas
été effectué ; le téléversement et sa confirmation restent à la charge de l'étudiant.
