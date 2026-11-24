---
title: Claim Coverage Checker
emoji: 🏠
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

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

## Application

Une page web (`/`) et une API (`/docs`) instruisent un sinistre de
démonstration ou un nouveau sinistre saisi dans le formulaire : verdict,
statut de chacun des 7 contrôles, clause et page citées, questions à poser.

| Route | Rôle |
|---|---|
| `GET /health` | l'API répond |
| `GET /ready` | base, classifieur, Ollama et modèle disponibles (503 sinon) |
| `GET /version` | version et modèle configuré |
| `GET /api/polices`, `GET /api/sinistres` | données de démonstration |
| `POST /api/instruire` | instruit `{"sinistre_id": "S-01"}` ou un nouveau sinistre |

Les sinistres saisis dans l'interface sont gardés en mémoire : la base livrée
n'est jamais modifiée.

## Démarrage local

Avec Docker (identique au Space) :

```bash
docker build -t claim-coverage-checker .
docker volume create donnees
docker run -p 7860:7860 -v donnees:/data claim-coverage-checker
```

Le volume `donnees` garde le modèle téléchargé (`llama3.2:3b`) : seul le
premier démarrage le télécharge. L'application est prête quand
<http://localhost:7860/ready> répond `ready`. Vérification de bout en bout :

```bash
python evaluation/verifier_application.py --url http://localhost:7860
```

Mémoire nécessaire : environ 6 Go libres. En secours, une adresse publique
temporaire s'obtient sans ouvrir de port avec
`cloudflared tunnel --url http://localhost:7860`.

Sans Docker (Ollama installé et lancé séparément) :

```bash
pip install -r requirements-app.txt
ollama pull llama3.2:3b
OLLAMA_MODEL=llama3.2:3b uvicorn src.app:app --port 7860
```

Sous Windows (PowerShell, Ollama pour Windows lancé) :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\lancer_local_windows.ps1
```

`USE_LLM=0` lance l'application sans modèle : les contrôles 4 à 6 restent
« à vérifier » avec les clauses à lire.

## Installation (développement)

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
python evaluation/evaluer_instruction.py --sans-modele   # évaluation de bout en bout, référence sans modèle
python evaluation/evaluer_instruction.py --repetitions 2 # même évaluation avec le modèle (Ollama lancé)
```

## Évaluation de bout en bout

`evaluation/cas_couverture.csv` : 13 sinistres × 3 contrats = 39 jugements,
répartis à l'avance en dev / test. Pour chacun : police, verdict attendu,
verdicts acceptables et fragment de la clause décisive, retrouvé mot pour mot
dans les conditions générales. Catégories : garanties de base (incendie,
foudre, dégât des eaux, tempête, fumée), exclusions (fait intentionnel,
usure), demandes hors du contrat habitation (pare-brise, assurance décès,
annulation de voyage, frais d'hôpital) et les deux cas du sujet (vélo,
bougie). Mesures : verdict exact, fausse couverture, faux refus, clause
décisive transmise au modèle ; intervalles de Wilson à 95 %. Le workflow
GitHub « Évaluation de bout en bout de l'instruction » exécute la mesure avec
le modèle.

Si la version de scikit-learn installée diffère de celle qui a entraîné le
modèle, réentraîner le classifieur (`python -m src.classifier`, une seconde).

## Versions

Numéro de version dans `VERSION` ; historique dans `CHANGEMENTS.md`.

## Données

Uniquement des documents publics et des données synthétiques.
