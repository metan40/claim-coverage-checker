# Conception — vérifier la couverture d'un sinistre comme un gestionnaire

## 1. Le principe

Un gestionnaire ne « lit pas le contrat pour voir si c'est couvert ». Il
**instruit** le sinistre selon une suite de contrôles toujours la même, du
plus simple au plus fin. Chaque contrôle a une source de vérité différente :
le portefeuille (conditions particulières), la déclaration, ou les
conditions générales. Le système reproduit cette instruction :

- les contrôles **factuels** sont faits en SQL, sans modèle de langage ;
- seuls les contrôles **d'interprétation** d'une clause font appel au LLM,
  sur les seules clauses concernées ;
- le verdict n'est pas « deviné » : il **découle** du résultat des contrôles.

C'est un découpage explicite du problème, et la réponse à la question
« comment tenir des centaines de contrats ? » : ce qui est structuré est
interrogé, ce qui est rédigé est cherché puis interprété.

## 2. L'instruction d'un sinistre en 7 contrôles

| # | Contrôle | Question | Source | Moyen | Issue possible |
|---|---|---|---|---|---|
| 1 | Contrat en vigueur | La police était-elle active à la date de survenance ? | Police | SQL | bloquant si non |
| 2 | Version applicable | Quelles conditions générales s'appliquent à cette date ? | Police + catalogue | SQL | — |
| 3 | Garantie souscrite | La garantie concernée (vol, pack mobilité…) fait-elle partie de la formule ou des options ? | Police (options) + catalogue des garanties | classifieur + SQL | bloquant si non souscrite |
| 4 | Événement et bien garantis | L'événement entre-t-il dans la définition de la garantie ? Le bien est-il un bien assuré, au bon endroit ? | Conditions générales (garantie, définitions) | recherche + LLM | hors champ / ambigu |
| 5 | Exclusions | Une exclusion, spécifique ou générale, s'applique-t-elle ? | Conditions générales (exclusions) | recherche + LLM | bloquant si oui |
| 6 | Conditions et obligations | Les conditions de garantie (fermeture à clé, antivol) et les obligations après sinistre (délai de déclaration, plainte) sont-elles remplies ? | Déclaration + conditions générales | SQL (délais) + LLM (conditions) | réduction, déchéance, ou information manquante |
| 7 | Montant | Plafond, franchise, valeur à neuf ou vétusté | Police + conditions générales | SQL + calcul | indemnisation estimée |

Chaque contrôle rend l'un de quatre statuts : **satisfait**, **bloquant**,
**à vérifier** (une information manque) ou **sans objet**. Le verdict en
découle par une règle explicite :

- un contrôle **bloquant** vérifié → **potentiellement exclu** (ou non
  couvert), avec sa nature : non souscrite, hors champ, exclusion,
  déchéance ;
- tous les contrôles **satisfaits** → **potentiellement couvert**, avec
  l'indemnisation estimée ;
- sinon → **indéterminé**, avec la liste précise de ce qui manque.

## 3. Les deux cas du sujet, instruits

**Le vélo dans le local commun non fermé à clé**

| Contrôle | Sogessur (FR) | Ethias (BE) | Baloise (LU) |
|---|---|---|---|
| 3 Garantie souscrite | vol : formule Initiale + option Vol, Confort ou Optimale → selon la police | vol optionnel (art. 4) → selon la police | vol optionnel ; pack mobilité durable → selon la police |
| 4 Bien garanti | vélo = bien mobilier | « tous types de vélos » assurés | vélo = objet de mobilité durable (si pack) |
| 5 Exclusions | **vol dans les locaux à usage commun : bloquant** ; vélo non attaché à un point fixe exclu (packs) | **vol dans les parties communes sans effraction (art. 4.4) : bloquant** si l'assuré n'occupe qu'une partie de l'immeuble | aucune exclusion directe trouvée |
| 6 Conditions | — | effraction ? | portes fermées à clé en cas d'absence (sinon réduction) ; antivol dans l'espace public |
| Verdict | **potentiellement exclu** (exclusion) | **potentiellement exclu** si pas d'effraction ; à vérifier sinon | **indéterminé** : pack souscrit ? le local commun relève-t-il des conditions de fermeture ? |

**La bougie fondue par la chaleur sur la table de jardin**

| Contrôle | Sogessur (FR) | Ethias (BE) | Baloise (LU) |
|---|---|---|---|
| 3 Garantie souscrite | — | — | mobilier de jardin : garantie optionnelle « Jardin » → selon la police |
| 4 Événement garanti | pas d'incendie | incendie = flammes et embrasement : **hors champ** | « dommages ménagers » : excès de chaleur sans embrasement, mais « action subite » |
| 5 Exclusions | **chaleur sans incendie : bloquant** | — | — |
| Verdict | **potentiellement exclu** (exclusion) | **non couvert** (hors champ) | **indéterminé** : garantie Jardin souscrite ? la chaleur de l'été est-elle « subite » ? une table de jardin est-elle un « objet d'ameublement » ? |

### Contrôle 6 : obligations après sinistre selon le droit applicable

Le non-respect d'une obligation après sinistre (déclaration tardive, par
exemple) n'entraîne pas de plein droit la perte de la garantie. Dans les
quatre droits francophones examinés, la sanction est proportionnée au
préjudice de l'assureur ; le refus total suppose une intention frauduleuse
ou un retard délibéré.

| Pays | Texte | Sanction de principe | Refus total |
|---|---|---|---|
| Luxembourg | Loi du 27 juillet 1997 sur le contrat d'assurance, art. 26 à 28 ; art. 18 | Réduction de la prestation à concurrence du préjudice subi (art. 28 §1) | Intention frauduleuse (art. 28 §2) ; toute déchéance contractuelle exige un lien causal avec le sinistre (art. 18) |
| Belgique | Loi du 4 avril 2014 relative aux assurances, art. 74 à 76 | Réduction à concurrence du préjudice (art. 76 §1) | Intention frauduleuse (art. 76 §2) |
| France | Code des assurances, art. L113-2 | Délai minimal de 5 jours ouvrés, 2 jours ouvrés en cas de vol | Déchéance opposable seulement si prévue au contrat et si l'assureur prouve un préjudice ; jamais en cas de force majeure |
| Suisse | Loi sur le contrat d'assurance (LCA), art. 38 et 45 | Réduction de l'indemnité à ce qu'elle aurait été avec un avis en temps utile, en cas de faute (art. 38 al. 2) | Retard intentionnel destiné à empêcher la vérification (art. 38 al. 3) ; aucune sanction si la violation n'est pas imputable ou sans incidence (art. 45) |

Règle appliquée par l'outil : un délai dépassé donne le statut **à
vérifier**, accompagné des questions « le retard a-t-il causé un préjudice à
l'assureur ? » et « une raison explique-t-elle le retard ? ». Le statut
**bloquant** n'est jamais déduit d'une date seule ; il relève du constat du
gestionnaire. La loi luxembourgeoise impose en outre que toute limitation ou
exclusion de garantie soit mise en évidence (art. 16 §2) : l'outil cite
chaque exclusion séparément, avec sa page.

## 4. Le modèle de données

```
contrats (conditions générales, une ligne par version)
  ├── articles ── article_familles          (clauses typées, index BM25)
  ├── definitions                           (termes définis)
  └── garanties                             (catalogue : garantie, base ou optionnelle, clauses d'en-tête)
polices (conditions particulières : démonstration + portefeuille synthétique)
  ├── police_options                        (options et packs souscrits)
  └── sinistres                             (déclarations)
        └── analyses                        (une instruction : verdict, version utilisée)
              └── controles                 (les 7 contrôles : statut, source, clause citée, preuve)
imports                                     (rapport de chaque import de contrat)
```

| Table | Rôle | Clés et colonnes principales |
|---|---|---|
| contrats | Conditions générales, versionnées | code, gamme, assureur, pays, date d'effet, empreinte du PDF |
| articles | Clauses | contrat, page début et fin, section, type, texte |
| article_familles | Clause ↔ familles | (article, famille) |
| definitions | Lexique du contrat | contrat, terme, clause |
| **garanties** | Ce que propose chaque contrat | contrat, famille, libellé, base ou optionnelle, formules qui l'incluent, clause d'en-tête |
| **polices** | Portefeuille | numéro, gamme, formule, date d'effet, échéance, statut, pays, plafonds, franchise ; assuré pseudonymisé |
| **police_options** | Options souscrites | (police, option) |
| **sinistres** | Déclarations | police, dates de survenance et de déclaration, description, lieu, bien, montant estimé, plainte, effraction, statut |
| **analyses** | Instructions | sinistre, version de contrat, famille prédite et probabilités, verdict, nature, indemnisation estimée, modèle, durée, avis du gestionnaire |
| **controles** | Le détail d'une instruction | analyse, numéro de contrôle, statut, source, clause citée et extrait vérifié, question à poser |
| imports | Traçabilité des imports | contrat, date, durée, clauses par type, statut, message |

Le catalogue des **garanties** est le pont entre le portefeuille et les
conditions générales. Il est extrait une fois par contrat (proposé à partir
des en-têtes de garantie, validé par un humain), puis réutilisé pour tous
les sinistres. C'est ce qui permet de tenir des centaines de contrats sans
relire leur texte à chaque question.

### Réalisation (version 4)

- **Catalogue des garanties** (`data/garanties/garanties.csv`, 18 garanties) :
  pour chaque garantie, sa famille, son statut (base, incluse dans une
  formule, option, extension pour un bien), la page et un fragment du texte
  qui la fonde. À l'import, chaque garantie est reliée à sa clause ; une
  garantie dont le fragment est introuvable fait échouer l'import. Le
  catalogue est **proposé** à partir des conditions générales et doit être
  **validé par un expert produit** avant mise en service (colonne
  `validation`).
- **Délais de déclaration** par contrat dans le catalogue des contrats :
  Baloise 8 jours (p.39), Ethias 10 jours (p.20), Sogessur 5 jours ouvrés et
  2 jours ouvrés pour le vol (p.31).
- **Polices et sinistres de démonstration** : 7 polices et 11 sinistres
  fictifs couvrant les deux cas du sujet sur les trois contrats, avec les
  situations qui font varier le verdict (option non souscrite, contrat
  résilié, déclaration tardive, pack jardin).
- **Portefeuille synthétique** : `python -m src.portefeuille 100000`.
  Test de charge : 100 000 polices, contrôles factuels en 0,1 ms par sinistre
  (`evaluation/resultats_charge_instruction.md`).
- **Contrôles factuels** (`src/instruction.py`) : contrôles 1, 2, 3, délai de
  déclaration et montant ; règle de verdict non compensatoire. Les contrôles
  4, 5 et 6 (conditions) sont marqués « à vérifier » en attendant
  l'interprétation des clauses.

Limites connues : jours fériés non déduits du calcul des jours ouvrés ;
vétusté non appliquée (l'indemnité est estimée avant vétusté) ; catalogue
limité aux garanties nécessaires aux cas étudiés.

## 5. Le rôle de chaque technique

| Technique | Où | Pourquoi là |
|---|---|---|
| SQL (sujet 2) | contrôles 1, 2, 3, 6 (délais), 7 | des faits : exacts, instantanés, auditables |
| Classifieur ML (sujet 4) | contrôle 3 | savoir quelle garantie examiner ; probabilité pour la règle de rejet |
| Recherche BM25 + synonymes | contrôles 4, 5, 6 | retrouver les clauses à interpréter, jamais le contrat entier |
| LLM, sortie JSON | contrôles 4, 5, 6 | interpréter une clause face aux faits ; une question fermée par contrôle |
| Vérification par l'application | tous | citations vérifiées, verdict déduit des contrôles et non déclaré par le modèle |

## 6. Ce que voit le gestionnaire

Un écran d'instruction : les 7 contrôles en liste, chacun avec son statut,
sa source (police, déclaration ou clause avec page), et pour les contrôles
« à vérifier » la question exacte à poser à l'assuré. Le verdict et
l'indemnisation estimée en tête ; la mention « aide à la décision » ; un
écran de comparaison qui instruit le même sinistre sur plusieurs contrats.
