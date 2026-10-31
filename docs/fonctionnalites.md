# Fonctionnalités de l'application (MVP)

L'application est une **aide à la décision** pour le gestionnaire de
sinistres. Elle ne rend jamais une décision contractuelle définitive : chaque
résultat renvoie aux clauses qui le justifient, avec leur page, et signale
ce qu'il est impossible de trancher avec les conditions générales seules.

Parcours : importer (ou choisir) un contrat → décrire le sinistre →
analyser la couverture → lire l'explication.

---

## F1 — Importer un contrat

L'utilisateur choisit un contrat déjà chargé ou importe un PDF de
conditions générales.

- Extraction du texte, des sections (chemin des titres) et des pages
  (`src/pdf_parsing.py`).
- Typage de chaque clause (définition, exclusion, condition, garantie) et
  rattachement aux familles de garanties (`src/database.py`).
- Enregistrement dans la base SQLite, avec l'empreinte SHA-256 du fichier
  (un même PDF n'est pas importé deux fois).
- **Rapport d'import** affiché : nombre de pages et de clauses, répartition
  par type, liste des sections. L'utilisateur juge lui-même la qualité du
  découpage.
- Refus explicite d'un PDF sans texte (document scanné) : pas d'OCR dans le
  MVP.

Trois contrats de référence sont préchargés : Baloise (Luxembourg), Ethias
(Belgique), Sogessur (France).

**Critères d'acceptation**
- Les trois contrats de référence sont importés sans erreur.
- Les clauses décisives des cas de test sont présentes, avec la bonne page
  et le bon type (tests automatisés).
- L'import d'un contrat prend moins de 15 secondes.

## F2 — Décrire un sinistre

L'utilisateur choisit un contrat et décrit librement l'événement (vol,
incendie, dégât des eaux, dommage matériel…). Des exemples sont proposés
(vélo volé dans le local commun, table de jardin fondue par une bougie).

- **Modèle ML** (TF-IDF + régression logistique calibrée) : prédit la ou les
  familles de garanties concernées avec une probabilité.
- Si le modèle hésite (probabilité maximale faible), les deux familles les
  plus probables sont retenues au lieu d'une seule.

**Critères d'acceptation**
- F1 macro mesuré sur un jeu de test tenu à part, matrice de confusion
  publiée.
- La famille correcte figure parmi les familles retenues pour les cas de
  test du sujet.

## F3 — Analyser la couverture

1. **Recherche des clauses** dans le contrat choisi uniquement : garanties
   et conditions des familles prédites, plus systématiquement les
   **exclusions** et les **définitions** des termes du sinistre (recherche
   plein texte BM25). Le document n'est jamais transmis en entier au modèle
   de langage.
2. **Réponse structurée** produite par le LLM (JSON imposé) :
   - verdict : `potentiellement couvert`, `potentiellement exclu` ou
     `indéterminé` ;
   - clauses citées (identifiant, page, extrait) ;
   - conditions à vérifier ;
   - informations manquantes.
3. **Vérification par l'application**, qui a le dernier mot :
   - une clause citée doit exister dans la base et l'extrait doit figurer
     dans son texte ; sinon elle est retirée ;
   - un verdict sans aucune clause vérifiée devient `indéterminé` ;
   - une garantie optionnelle ou dépendant de la formule souscrite ajoute
     l'information manquante « garantie souscrite aux conditions
     particulières ? ».

Un « indéterminé » justifié vaut mieux qu'un verdict non justifié.

**Critères d'acceptation**
- Aucune clause affichée n'est absente du contrat (contrôle automatique).
- Sur les cas de test (`evaluation/cas_de_test.csv`), le verdict attendu
  est atteint ou l'analyse répond `indéterminé` en nommant l'information
  qui manque.

## F4 — Expliquer le résultat

L'interface affiche :

- le verdict, accompagné de la mention permanente « aide à la décision —
  pas une décision contractuelle » ;
- les clauses citées : type, section, page, extrait surligné ;
- les conditions applicables (ex. antivol relié à un point fixe, portes
  fermées à clé) ;
- les informations manquantes, formulées comme des questions à poser à
  l'assuré (ex. « Le local commun est-il fermé à clé ? ») ;
- la famille prédite par le modèle ML et sa probabilité.

Chaque analyse est enregistrée dans la table `decisions` (date, contrat,
sinistre, réponse, modèle, durée) pour la traçabilité.

**Critères d'acceptation**
- Chaque clause affichée indique sa page et son type.
- La mention « aide à la décision » figure sur chaque résultat.

---

## Hors MVP (pistes ultérieures)

- Comparer un même sinistre sur plusieurs contrats en un écran.
- Lire les conditions particulières (formule et options souscrites).
- OCR pour les PDF scannés ; contrats en néerlandais ou en allemand.
- Comptes utilisateurs et conservation des contrats importés (sur le Space
  gratuit, les imports sont perdus au redémarrage).
