# claim-coverage-checker

Aide à l'instruction des sinistres habitation : dire si un sinistre est
couvert, sur quelles clauses, et ce qu'il manque pour conclure.

L'outil instruit un sinistre selon les contrôles d'un gestionnaire
(contrat en vigueur, garantie souscrite, événement garanti, exclusions,
conditions, montant), cite chaque clause avec sa page et répond
« indéterminé » quand le contrat ne permet pas de conclure. Il prépare la
décision ; le gestionnaire la prend.

## Contenu

| Dossier | Rôle |
|---|---|
| `src/` | découpage des PDF, base SQLite, classifieur, recherche des clauses, instruction, décision |
| `data/conditions_generales/` | conditions générales publiques (LU, BE, FR) et catalogue |
| `data/sinistres/` | descriptions de sinistres synthétiques (entraînement, test) et sinistres de démonstration |
| `data/garanties/` | catalogue des garanties de chaque contrat |
| `data/portefeuille/` | polices de démonstration |
| `db/` | base SQLite construite à partir des PDF |
| `models/` | classifieur entraîné |
| `evaluation/` | scripts et résultats d'évaluation |
| `tests/` | tests automatisés |
| `docs/` | note de cadrage, conception, méthodes, journal technique |

## Installation

Python 3.11 ou plus récent.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Utilisation

```bash
python -m pytest -q                          # tests
python -m src.database                       # reconstruit la base à partir des PDF
python -m src.instruction S-01               # instruit un sinistre de démonstration (S-01 à S-11)
python -m src.portefeuille 100000            # ajoute un portefeuille synthétique de 100 000 polices
python -m src.classifier                     # réentraîne le classifieur
python evaluation/evaluate_classifier.py     # évalue le classifieur
python evaluation/evaluate_retrieval.py      # évalue la recherche des clauses
python evaluation/test_charge_instruction.py # test de charge des contrôles factuels
```

Si la version de scikit-learn installée diffère de celle qui a entraîné le
modèle, réentraîner le classifieur (`python -m src.classifier`, une seconde).

## Versions

Numéro de version dans `VERSION` ; historique dans `CHANGEMENTS.md`.

## Données

Uniquement des documents publics et des données synthétiques.
