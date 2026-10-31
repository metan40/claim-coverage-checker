# Historique des versions

Une version = une archive `claim-coverage-checker_vN.zip`. Le détail des
décisions et des mesures est dans `docs/journal_technique.md`.

## Version 2 — 31 octobre 2026

- Schémas dans `docs/schemas/` : processus d'instruction (BPMN 2.0, importable dans Bizagi et Enterprise Architect), architecture, modèle de données, séquence d'une instruction, import d'un contrat, cas d'utilisation.
- Chaque schéma fourni en source modifiable, SVG et PNG ; mode d'emploi dans `docs/schemas/README.md`.

## Version 1 — 31 octobre 2026

- Découpage générique des conditions générales PDF en clauses citables (3 contrats : LU, BE, FR).
- Base SQLite : contrats versionnés, clauses typées, familles, définitions, index plein texte BM25.
- Classifieur des descriptions de sinistres (régression logistique TF-IDF, 90 % sur un test indépendant) et banc d'essai des modèles modernes.
- Recherche des clauses : BM25, synonymes métier, quotas, en-têtes de garantie (12 clauses décisives sur 14).
- Décision : réponse JSON du modèle de langage, vérifiée par l'application (citations, cohérence du verdict).
- Expériences SVD : recherche (non retenue) ; visualisation et regroupement (outil de diagnostic).
- Documentation : note de cadrage, conception en 7 contrôles, méthodes, journal technique.
- 51 tests automatisés.
