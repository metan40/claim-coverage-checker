# Comprendre le code de claim-coverage-checker (version 5)

Ce document explique chaque fichier Python de `src/`. Pour chaque fichier, il
donne son rôle, la technique utilisée et ses fonctions principales : ce
qu'elles reçoivent, ce qu'elles font et ce qu'elles renvoient.

## Le chemin d'un sinistre dans le code

1. `pdf_parsing.py` découpe chaque PDF de conditions générales en clauses.
2. `database.py` range les clauses, les contrats, les garanties et les polices dans SQLite.
3. `classifier.py` lit la description du sinistre et prédit la famille de garantie (vol, incendie…).
4. `instruction.py` fait les contrôles factuels : contrat, version, garantie, délai, montant.
5. `retrieval.py` trouve les clauses du contrat qui parlent du sinistre.
6. `interpretation.py` pose 3 questions fermées au modèle de langage sur ces clauses.
7. `decision.py` appelle Ollama et vérifie que l'extrait cité existe dans la clause.
8. `instruction.py` combine les 7 contrôles en un verdict.
9. `app.py` affiche le résultat dans la page web.

---

## 1. `pdf_parsing.py` : lire les conditions générales

**Rôle.** Transformer un PDF en une liste de clauses citables, chacune avec son titre de section et sa page.

**Technique.** Lecture des mots et de leur position avec `pdfplumber`. Règles de mise en page : colonnes, tailles de police, gras.

| Fonction | Reçoit | Fait | Renvoie |
|---|---|---|---|
| `read_lines(pdf_path)` | chemin du PDF | lit chaque page, détecte les deux colonnes, regroupe les mots en lignes | liste de `Line` (texte, taille, gras, page) |
| `column_gutter(words, width)` | mots d'une page, largeur | cherche une verticale vide entre 40 % et 60 % de la largeur | abscisse de la gouttière, ou `None` |
| `is_table_of_contents(lines)` | lignes d'une page | repère un sommaire (lignes finissant par un numéro de page) | vrai ou faux |
| `remove_running_headers(lines, n)` | toutes les lignes | supprime les en-têtes et pieds de page répétés | lignes nettoyées |
| `body_font_size(lines)` | lignes | prend la taille de police la plus fréquente | taille du corps de texte |
| `heading_sizes(lines, body)` | lignes, taille du corps | trouve les tailles plus grandes, groupées par niveaux | tailles de titres |
| `heading_level(line, …)` | une ligne | décide si c'est un titre (grande taille ou gras) et de quel niveau | niveau 1, 2… ou `None` |
| `build_passages(lines)` | lignes | regroupe le texte sous chaque titre | liste de `Passage` |
| `parse_contract(pdf_path)` | chemin du PDF | enchaîne toutes les étapes ; coupe les passages trop longs, fusionne les trop courts | clauses du contrat |

**Résultat.** 323 clauses pour Baloise, 232 pour Ethias et 444 pour Sogessur.

## 2. `database.py` : la base de données

**Rôle.** Construire et lire la base SQLite `db/contrats.sqlite`.

**Technique.** SQLite (une base dans un seul fichier), avec l'index plein texte FTS5 pour la recherche BM25.

| Fonction | Reçoit | Fait | Renvoie |
|---|---|---|---|
| `normalize(text)` | texte | minuscules, sans accents, espaces uniformisés | texte normalisé |
| `article_type(section, text)` | titre et texte d'une clause | classe la clause par mots clés : définition, exclusion, condition ou garantie | le type |
| `article_families(section, text)` | titre et texte | repère les familles citées (vol, incendie…) | liste de familles |
| `create_database(db_path)` | chemin | crée les tables (contrats, articles, garanties, polices, sinistres…) | connexion |
| `insert_contract(…)` | contrat et ses clauses | enregistre le contrat et ses clauses, avec leur type et leurs familles | identifiant du contrat |
| `load_guarantees(…)` | catalogue `garanties.csv` | charge les garanties ; relie chacune à la clause qui la fonde | nombre de garanties |
| `load_demo(…)` | polices et sinistres de démonstration | charge les 11 sinistres et leurs polices, fictifs | nombres chargés |
| `build_database(…)` | catalogue des PDF | reconstruit toute la base | résumé par contrat |
| `applicable_version(…)` | gamme, date du sinistre | choisit la version des conditions générales en vigueur à cette date | la version, ou `None` |
| `connect(db_path)` | chemin | ouvre la base en lecture | connexion |

## 3. `classifier.py` : reconnaître le type de sinistre

**Rôle.** À partir de la description libre, prédire la famille de garantie concernée.

**Technique.** TF-IDF (mots et fragments de 2 à 5 lettres), puis régression logistique multinomiale. 90 % de bonnes réponses sur un test indépendant.

| Fonction | Reçoit | Fait | Renvoie |
|---|---|---|---|
| `load(path)` | fichier CSV | lit les descriptions et leurs familles | textes, familles |
| `candidates()` | — | définit les algorithmes comparés (régressions logistiques, SVM…) | dictionnaire de modèles |
| `train(name)` | nom du modèle | entraîne sur `sinistres_entrainement.csv` | modèle entraîné |
| `predict(model, text)` | modèle, description | calcule une probabilité par famille ; si la meilleure est sous 0,60, garde aussi la deuxième | `Prediction` (familles, probabilités) |
| `explain(model, text, family)` | modèle, description, famille | calcule la contribution de chaque mot : valeur TF-IDF × coefficient | mots qui ont le plus pesé |
| `save` / `load_model` | modèle ou chemin | enregistre ou relit `models/classifieur_sinistres.joblib` | — / modèle |

## 4. `retrieval.py` : trouver les clauses utiles

**Rôle.** Pour un contrat donné, trouver les clauses qui concernent le sinistre.

**Technique.** Recherche BM25 de SQLite FTS5. Elle est complétée par des synonymes métier et par des quotas par type de clause.

| Fonction | Reçoit | Fait | Renvoie |
|---|---|---|---|
| `stem(token)` | un mot | retire un suffixe courant (« volés » → « vol ») | racine |
| `query_terms(description)` | description | garde les mots significatifs et ajoute les synonymes (« local commun » → « locaux à usage commun ») | termes de recherche |
| `fts_query(terms)` | termes | écrit la requête FTS5 : `racine*` pour les mots, guillemets pour les expressions, `OR` entre eux | requête texte |
| `_candidates(…)` | contrat, requête | lance BM25 sur les clauses de ce seul contrat | 80 meilleures clauses |
| `_definitions_for_terms(…)` | contrat, termes | ajoute les définitions des mots de la description | définitions |
| `_guarantee_headers(…)` | contrat, familles | ajoute le début de chaque garantie concernée | en-têtes de garantie |
| `retrieve(…)` | contrat, description, familles | multiplie par 1,5 le score des clauses des familles prédites ; retient au plus 2 en-têtes, 5 garanties ou conditions, 5 exclusions, 4 définitions | liste ordonnée de `Clause` |

## 5. `concepts.py` : le dictionnaire des mots métier

**Rôle.** Relier les mots de l'assuré, jargon compris (« DDE », « kot »), aux mots du contrat.

**Technique.** Fichier `data/concepts/concepts.csv` et recherche d'expressions. Ce fichier n'est pas encore branché sur la recherche.

| Fonction | Reçoit | Fait | Renvoie |
|---|---|---|---|
| `load()` | — | lit les 36 concepts | concepts |
| `detect(description)` | description | repère les concepts présents | concepts et terme déclencheur |
| `contract_terms(description)` | description | donne les mots du contrat correspondants | termes à ajouter à la recherche |
| `lexicon(description)` | description | prépare un petit lexique pour le prompt | texte |

## 6. `decision.py` : appeler le modèle et vérifier ses extraits

**Rôle.** Parler à Ollama et contrôler ce que le modèle cite.

**Technique.** API HTTP d'Ollama, réponse JSON imposée par un schéma, température 0 (même question, même réponse).

| Fonction | Reçoit | Fait | Renvoie |
|---|---|---|---|
| `call_ollama(prompt, schema)` | texte de la question, schéma JSON | envoie la demande à `llama3.2:3b` (contexte de 4 096 tokens, 400 tokens de réponse au plus) | texte JSON du modèle |
| `extract_is_in_clause(extract, clause)` | extrait cité, texte de la clause | accepte si l'extrait est dans la clause, ou si au moins 80 % de ses mots y sont | vrai ou faux |
| `build_prompt`, `verify`, `analyse` | description, clauses | ancienne analyse en un seul appel (version 3), gardée pour comparaison | `Decision` |
| `record(…)` | connexion, analyse | enregistre l'analyse dans la base | identifiant |

## 7. `interpretation.py` : les 3 questions fermées

**Rôle.** Faire les contrôles 4, 5 et 6, qui demandent de lire les clauses.

**Technique.** Une question fermée par contrôle. Réponse imposée : « oui », « non » ou « incertain », avec une clause et un extrait.

| Contrôle | Question posée au modèle | Clauses fournies |
|---|---|---|
| 4 | L'événement et le bien entrent-ils dans ce que les clauses garantissent ? | garanties, définitions |
| 5 | Une des exclusions fournies s'applique-t-elle ? | exclusions |
| 6 | Les conditions de garantie sont-elles remplies ? | conditions |

| Fonction | Reçoit | Fait | Renvoie |
|---|---|---|---|
| `selection(clauses, numero)` | clauses, numéro du contrôle | garde seulement le type de clause utile | clauses |
| `prompt(numero, description, faits, clauses)` | faits et clauses | écrit la question | texte |
| `interpreter(…)` | idem, et le modèle | interroge le modèle, vérifie l'extrait, puis décide du statut | `Controle` |

**Règles de statut :**
- Sans extrait vérifié, le contrôle reste « à vérifier ».
- Une exclusion vérifiée rend le contrôle 5 « bloquant ».
- Une condition non remplie reste « à vérifier », sans bloquer : la loi exige un lien avec le sinistre.

## 8. `instruction.py` : les 7 contrôles et le verdict

**Rôle.** Instruire un sinistre du début à la fin.

**Technique.** Requêtes SQL et calculs pour les contrôles factuels. Agrégation des contrôles par une règle non compensatoire.

| Fonction | Reçoit | Fait | Renvoie |
|---|---|---|---|
| `controle_contrat(police, date)` | police, date du sinistre | vérifie que le contrat était en vigueur | contrôle 1 |
| `controle_version(…)` | gamme, date | trouve les conditions générales applicables | contrôle 2 |
| `controle_garantie(…)` | contrat, police, options, familles, bien | vérifie que la garantie est de base, dans la formule ou en option | contrôle 3 et garanties retenues |
| `controles_interpretation(…)` | contrat, sinistre, familles, modèle | cherche les clauses, puis pose les 3 questions | contrôles 4, 5, 6 |
| `jours_ouvres(debut, fin)` | deux dates | compte les jours du lundi au vendredi | nombre de jours |
| `controle_delai(…)` | contrat, sinistre | compare le délai de déclaration au délai du contrat | contrôle 6 (délai) |
| `indemnite(D, F, P)` | dommage, franchise, plafond | calcule I = min(max(D − F, 0), P) | indemnité |
| `controle_montant(…)` | police, garanties, montant | applique la franchise et le plafond | contrôle 7 et indemnité |
| `verdict(controles)` | les contrôles | un contrôle bloquant → « exclu » ; tous satisfaits → « couvert » ; sinon → « indéterminé » | verdict et nature |
| `instruire(connexion, id, familles, modèle)` | un sinistre | enchaîne tout | `Instruction` complète |
| `afficher(instruction)` | instruction | met en forme pour le terminal | texte |

## 9. `app.py` : l'application web

**Rôle.** Donner une page web et une API au reste du code.

**Technique.** FastAPI. Une copie de la base est gardée en mémoire : la base livrée n'est jamais modifiée.

| Route | Fait |
|---|---|
| `GET /` | affiche la page `static/index.html` |
| `GET /ready` | vérifie la base, le classifieur, Ollama et le modèle |
| `GET /api/polices`, `GET /api/sinistres` | listent les données de démonstration |
| `POST /api/instruire` | instruit un sinistre de démonstration ou un nouveau sinistre saisi |

## 10. `portefeuille.py` : tester à grande échelle

**Rôle.** Créer un portefeuille fictif de polices, par exemple 100 000, pour mesurer la vitesse des contrôles factuels.

| Fonction | Reçoit | Fait | Renvoie |
|---|---|---|---|
| `generer(n, seed)` | nombre de polices, graine aléatoire | tire des polices et des options au hasard, toujours les mêmes pour une graine donnée | lignes à insérer |
| `ajouter(n)` | nombre de polices | remplace le portefeuille fictif de la base | nombres insérés |

## 11. Les autres fichiers Python

| Fichier | Rôle |
|---|---|
| `data/sinistres/generer_sinistres.py` | génère les descriptions fictives qui entraînent le classifieur |
| `evaluation/evaluate_classifier.py` | compare les algorithmes de classification sur le test indépendant |
| `evaluation/benchmark_modeles.py` | banc d'essai des classifieurs, du TF-IDF aux transformeurs |
| `evaluation/evaluate_retrieval.py` | vérifie que la recherche trouve les clauses décisives des deux cas du sujet (vélo, bougie) |
| `evaluation/experience_lsa.py` | expérience : la réduction SVD (analyse sémantique latente) améliore-t-elle la recherche ? |
| `evaluation/experience_svd_visualisation.py` | expérience : réduire la matrice TF-IDF par SVD pour visualiser les clauses |
| `evaluation/test_charge_instruction.py` | mesure la vitesse des contrôles factuels sur un grand portefeuille |
| `evaluation/evaluer_instruction.py` | évaluation de bout en bout sur 39 jugements (verdict exact, fausse couverture, faux refus) |
| `evaluation/verifier_application.py` | vérifie une application en marche, locale ou en ligne, par son API |

## Lancer en local

```powershell
cd $HOME\Desktop\claim-coverage-checker-v5
powershell -ExecutionPolicy Bypass -File scripts\lancer_local_windows.ps1
```

Puis ouvrir <http://localhost:7860/ready>, et <http://localhost:7860/> quand la page affiche « ready ».
