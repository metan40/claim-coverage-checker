# Les méthodes retenues

Douze méthodes, choisies parce que chacune résout un problème précis du
projet avec une formule simple que l'on peut expliquer au tableau. Rien
d'exotique : des outils éprouvés, appliqués au bon endroit.

| # | Problème à résoudre | Méthode | Formule ou règle | Pourquoi elle convient |
|---|---|---|---|---|
| 1 | Lire des contrats de mises en page différentes | Découpage selon la structure du document (colonnes, titres, clauses) | une clause = un passage sous son chemin de titres, avec sa page | une exclusion reste entière, citable avec sa page |
| 2 | Retrouver les clauses utiles sans donner tout le contrat au LLM | BM25 + synonymes métier | score = Σ IDF(t) · f(k₁+1) / (f + k₁(1 − b + b·\|d\|/moy)) | favorise les mots rares (« vélo », « effraction »), ne se laisse pas noyer par les répétitions |
| 3 | Savoir quelle garantie examiner | Régression logistique multinomiale (TF-IDF) | p(k \| x) = exp(β_kᵀx) / Σ_j exp(β_jᵀx) | probabilités utilisables, perte convexe, chaque prédiction s'explique par ses mots |
| 4 | Ne pas décider quand le modèle hésite | Règle de rejet de Chow | décider si max_k p(k \| x) ≥ 1 − r ; sinon renvoyer au gestionnaire (r = 0,4) | décision optimale quand un renvoi coûte moins qu'une erreur |
| 5 | Établir les faits du dossier | Requêtes SQL sur le portefeuille et la déclaration | police active si date d'effet ≤ date du sinistre < échéance ; délai = déclaration − survenance | exact, instantané, auditable : pas de LLM pour des faits |
| 6 | Interpréter une clause face aux faits | LLM en classification fermée (sortie JSON imposée) | réponse ∈ {oui, non, incertain} + clause + extrait | un format fermé se vérifie ; un texte libre, non |
| 7 | Empêcher les citations inventées | Mesure d'inclusion | \|mots(extrait) ∩ mots(clause)\| / \|mots(extrait)\| ≥ 0,8 | tolère une recopie imparfaite, rejette une invention |
| 8 | Conclure à partir des contrôles | Agrégation non compensatoire avec veto | exclu si un contrôle est bloquant ; couvert si tous sont satisfaits ; sinon indéterminé | le droit des assurances est non compensatoire : rien ne rachète une exclusion |
| 9 | Estimer l'indemnité | Calcul actuariel simple | I = min(max(D − F, 0), P), avec D le dommage (valeur à neuf ou après vétusté), F la franchise, P le plafond | donne au gestionnaire un ordre de grandeur, pas seulement un oui ou un non |
| 10 | Chiffrer le coût des erreurs | Coût attendu | E[C] = c_payer-à-tort · n₁ + c_refuser-à-tort · n₂ + c_renvoi · n₃ | relie le seuil de décision à l'argent et au risque client |
| 11 | Mesurer honnêtement | Précision, rappel, F1 macro, rappel@k ; intervalles de confiance par bootstrap ; test de McNemar | P = VP/(VP+FP), R = VP/(VP+FN) ; IC à 95 % par 2 000 tirages ; désaccords b, c ~ Binomiale(b + c, ½) sous H₀ | des chiffres vérifiables, avec leur incertitude ; un écart entre deux modèles n'est retenu que s'il est significatif |
| 12 | Choisir le modèle sur plusieurs critères | Dominance de Pareto puis PROMETHEE II | φ(a) = Σ_j w_j φ_j(a) (flux net) ; sensibilité aux poids | justifie un choix entre justesse, calibration, vitesse et explicabilité |

## Ce que l'on n'utilise pas, volontairement

Pas de réseau profond en production : le banc d'essai le compare, et l'on ne
le retient que s'il est significativement meilleur. Pas de somme pondérée
pour le verdict : elle laisserait une bonne garantie compenser une
exclusion. Pas de contrat entier dans le LLM : la recherche choisit 16
clauses au plus.
