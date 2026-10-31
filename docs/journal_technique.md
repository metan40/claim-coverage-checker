# Journal technique

Décisions, mesures et corrections, dans l'ordre chronologique.

## 30 octobre 2026

### Cadrage
- Sujet : vérifier la couverture d'un sinistre habitation à partir des conditions générales, en citant les clauses et en reconnaissant les cas indéterminés.
- Trois conditions générales publiques de trois pays, pour montrer que la même question reçoit des réponses différentes selon le contrat : Baloise Home (LU, CG-HOME(2)-LUFR-11-23), Ethias Habitation (BE, 1252-050 03/25), Sogessur Habitation (FR, F 190 315 04/2025).
- Uniquement des documents publics et des données synthétiques.

### Découpage des contrats (`src/pdf_parsing.py`)
Un seul code pour les trois contrats, sans règle propre à un assureur.

| Problème observé | Correction |
|---|---|
| Pages en deux colonnes lues ligne à ligne | Détection de la gouttière centrale, lecture colonne par colonne |
| Texte à lettres espacées | Tolérance d'espacement proportionnelle à la taille de police |
| Lignes de sommaire prises pour des titres | Saut des pages de sommaire |
| En-têtes de page pris pour des titres | Suppression des lignes de marge répétées |
| Titres numérotés pris pour des puces | Distinction entre puces symboliques et numéros de titre |
| Phrases d'exclusion en gras prises pour des titres | Règle de continuation d'une phrase en gras |
| Niveaux de titres écrasés | Regroupement des tailles de police en niveaux |
| Page à une colonne coupée en deux | Détection de gouttière fondée sur les lignes entières |
| Titre « CE QUI EST EXCLU » effacé comme en-tête | Une ligne répétée n'est un en-tête que si elle revient au même endroit de la page |
| Garanties écrites comme de simples titres perdues | Un titre sans texte suivi d'un titre de même niveau devient un passage |

Résultat : 323, 232 et 444 clauses ; 3 à 8 s par contrat.

### Base de données (`src/database.py`)
- SQLite, 5 tables et un index plein texte FTS5 (BM25, accents ignorés).
- Typage des clauses par règles. Correction : le titre « CONDITIONS GÉNÉRALES » classait tout un contrat en « condition » ; les conditions se lisent désormais sur le dernier titre.
- Version et date d'effet par contrat.

### Classifieur des sinistres (`src/classifier.py`)
- Entraînement : 780 descriptions générées ; test : 60 descriptions écrites à la main, dans d'autres tournures.
- Validation croisée à 1,00 pour tous les modèles : fuite due aux gabarits partagés. Seul le test indépendant est retenu.
- Régression logistique (mots et caractères) : 90 % d'exactitude (IC 95 % : 82–97 %), F1 macro 0,89.
- Règle de rejet : sous 60 % de confiance, deux familles sont retenues (bonne famille retenue dans 95 % des cas).
- Banc d'essai des modèles modernes (`evaluation/benchmark_modeles.py`). Correction : ordre des colonnes dans le calcul du log-loss.

### Recherche des clauses (`src/retrieval.py`)
- BM25 dans le seul contrat choisi, synonymes métier, familles prédites, contexte par quotas, 16 clauses au plus.
- Rappel des clauses décisives : 12/14 ; sans synonymes 7/14 ; sans classifieur 10/14 ; BM25 seul 11/14. Réglage fait sur ces cas : chiffre optimiste, à confirmer sur des cas nouveaux.

### Décision (`src/decision.py`)
- Sortie JSON imposée ; vérification des clauses et des extraits ; règles de cohérence du verdict ; questions du gestionnaire ; repli si le modèle ne répond pas ; traçabilité. Tests avec un modèle simulé.

### Relecture de l'énoncé
- Cas de la bougie : la bougie n'est pas allumée ; elle fond sous la chaleur et abîme la table. Pas de flamme, pas d'incendie, pas d'événement soudain. Jeu de test, clauses attendues et questions du gestionnaire à corriger.

## 31 octobre 2026

- Conception refondue : l'instruction d'un sinistre en 7 contrôles, le verdict découlant des contrôles ; modèle de données étendu (garanties, polices, options, sinistres, analyses, contrôles, imports). Voir `conception.md`.
- Douze méthodes retenues, chacune justifiée par un problème du projet. Voir `methodes.md`.
- Test de charge : 100 899 clauses (303 contrats), base de 110 Mo, recherche des clauses d'un contrat en 14 ms environ.
- Expérience SVD (analyse sémantique latente) sur la recherche des clauses (`evaluation/experience_lsa.py`). Matrice clauses × termes de 999 × 2 656, densité 1,2 %. Rappel des 14 clauses décisives dans les 16 premières : BM25 seul 11/14 ; LSA seule 5/14 (k = 50), 9/14 (k = 100), 10/14 (k = 200) ; fusion BM25 + LSA 10 à 11/14. **Conclusion : la SVD n'apporte rien ici.** Le corpus est petit et juridique : le mot exact compte (« effraction », « usage commun »), et la réduction de dimension dilue précisément ces termes rares. Le dictionnaire de synonymes métier reste plus efficace (7/14 sans, 12/14 avec, dans la chaîne complète). Décision : SVD non retenue.
- Expérience SVD pour visualiser et regrouper (`evaluation/experience_svd_visualisation.py`, figures dans `evaluation/figures/`). Trois constats :
  1. En 2D, la SVD ne conserve que 2,7 % de la variance des descriptions : une image en 2D d'un texte est illustrative, pas une mesure.
  2. **Décalage de distribution visible** : les descriptions de test écrites à la main se regroupent à part des descriptions générées. La première composante est portée par les formules répétées des gabarits (« Bonjour », « Que dois-je faire ? »). La figure explique pourquoi la validation croisée donnait 1,00 et le test 90 %.
  3. Le regroupement non supervisé (k-means) ne retrouve pas les familles (ARI 0,03 pour les sinistres comme pour les clauses) ; les clauses se regroupent davantage par assureur (ARI 0,17) que par garantie : le style de rédaction domine le sujet. D'où un classifieur supervisé pour les sinistres et un catalogue des garanties validé par un expert pour aligner les contrats entre eux.
