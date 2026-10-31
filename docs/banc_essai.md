# Banc d'essai des classifieurs

Le script `evaluation/benchmark_modeles.py` compare les classifieurs de
sinistres sur le même jeu de test indépendant : TF-IDF avec régression
logistique ou SVM calibré, plongements multilingual-e5 avec régression
logistique ou gradient boosting, SetFit, DistilCamemBERT ajusté, et un LLM
sans apprentissage.

## Installation

Un environnement avec accès à Internet est nécessaire (téléchargement des
modèles depuis Hugging Face, environ 500 Mo). Aucun GPU n'est requis.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements-benchmark.txt
```

## Exécution

```bash
python evaluation/benchmark_modeles.py --seulement tfidf_reglog   # vérification rapide
python evaluation/benchmark_modeles.py --camembert                # banc complet (15 à 30 min sur processeur)
python evaluation/benchmark_modeles.py --llm                      # ajoute llama3.2 (Ollama lancé)
```

## Résultats

Le script écrit `evaluation/resultats_benchmark.md` et `.json` : exactitude et
F1 macro avec intervalles de confiance à 95 % (bootstrap, 2 000 tirages),
top-2, log-loss, score de Brier, écart apparié avec la référence, temps
d'entraînement et de prédiction, taille du modèle, erreurs par modèle. Un
modèle en échec n'interrompt pas les autres.
