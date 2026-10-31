# Note de cadrage

**Projet** : claim-coverage-checker — Aide à l'instruction des sinistres habitation
**Version** : 1.0 — 31 octobre 2026
**Auteur** : T. MBARGA BYAKOLO
**Statut** : en cours de réalisation

---

## 1. Contexte

À chaque déclaration de sinistre habitation, le gestionnaire doit établir si
l'événement est couvert par le contrat de l'assuré. Cette instruction
croise trois sources : la déclaration, les conditions particulières
(formule, options, plafonds) et les conditions générales, document
juridique de 40 à 50 pages dont les définitions, garanties, exclusions et
conditions sont dispersées.

Le portefeuille d'un assureur comprend plusieurs produits habitation, chacun
en plusieurs versions successives. Le volume de texte à maîtriser croît
avec chaque nouveau produit et chaque révision.

## 2. Problème

L'instruction actuelle présente quatre faiblesses :

- **Durée** : la recherche et la relecture des clauses se répètent à chaque dossier.
- **Hétérogénéité** : deux gestionnaires peuvent retenir des clauses différentes pour un même cas.
- **Risque financier et client** : un paiement non dû augmente le coût des sinistres ; un refus injustifié génère réclamations, recours et atteinte à l'image.
- **Passage à l'échelle** : chaque nouveau produit ou version alourdit la charge de connaissance.

Les assistants conversationnels qui reçoivent le contrat entier ne
répondent pas au besoin : ils ne citent pas leurs sources de façon
vérifiable, produisent des réponses affirmatives même en l'absence de
fondement, et se dégradent quand le nombre de contrats augmente.

## 3. Objectif

Fournir au gestionnaire un outil d'**aide à la décision** qui, pour un
sinistre déclaré :

1. instruit le dossier selon les contrôles d'un gestionnaire ;
2. indique si le sinistre est potentiellement couvert, potentiellement exclu, ou indéterminé ;
3. cite chaque clause utilisée, avec sa page ;
4. formule les informations manquantes sous forme de questions à poser à l'assuré.

La décision reste celle du gestionnaire.

## 4. Périmètre

| Inclus | Exclu |
|---|---|
| Assurance habitation, garanties dommages et responsabilité civile | Autres branches (automobile, santé, prévoyance) |
| Conditions générales en PDF textuel, en français | PDF scannés (OCR), autres langues |
| Conditions particulières sous forme de table structurée | Lecture de conditions particulières en PDF |
| Instruction de la couverture et estimation de l'indemnité | Règlement, paiement, recours contre tiers |
| Données publiques et synthétiques | Données de clients réels |

## 5. Solution retenue

L'outil reproduit l'instruction d'un sinistre en sept contrôles : contrat
en vigueur, version applicable, garantie souscrite, événement et bien
garantis, exclusions, conditions et obligations, montant. Les contrôles
factuels reposent sur des requêtes en base de données ; les contrôles
d'interprétation reposent sur la recherche des clauses pertinentes et sur
un modèle de langage local dont chaque citation est vérifiée. Le verdict
découle des contrôles selon une règle explicite et non compensatoire.
Détail : `conception.md` et `methodes.md`.

## 6. Bénéfices attendus et indicateurs

| Bénéfice | Indicateur de suivi |
|---|---|
| Réduction du temps d'instruction | Durée moyenne d'instruction par dossier |
| Maîtrise du coût des sinistres | Montants réglés à tort, constatés à l'audit |
| Réduction des refus injustifiés | Taux de réclamations et de contestations |
| Homogénéité des décisions | Taux d'accord entre l'outil et les gestionnaires |
| Meilleure expérience client | Part des dossiers traités en un seul échange |
| Intégration rapide des nouveaux produits | Délai d'intégration d'un nouveau contrat |

Ordre de grandeur, à valider par un pilote : pour 20 000 sinistres
habitation par an, un gain de 10 minutes par dossier représente environ
3 300 heures de gestion.

## 7. Données et conformité

- Conditions générales publiques de trois assureurs (Luxembourg, Belgique, France).
- Portefeuille, sinistres et descriptions générés de façon synthétique et documentée.
- Modèle de langage exécuté localement : aucune donnée n'est transmise à un service externe.
- Traçabilité de chaque analyse ; mention « aide à la décision » sur chaque résultat.

## 8. Livrables

| Livrable | Description |
|---|---|
| Application en ligne | Interface web d'instruction et de comparaison des contrats |
| Code source | Dépôt versionné, tests automatisés, intégration continue |
| Base de données | Contrats découpés, catalogue des garanties, portefeuille synthétique |
| Rapport technique | Besoin, données, algorithme, restitution, évaluation, limites |
| Guide de vérification | Parcours de contrôle de l'application en 10 minutes |

## 9. Jalons

| Date | Jalon |
|---|---|
| 30 octobre 2026 | Découpage des contrats, base de données, classifieur, recherche des clauses |
| 31 octobre 2026 | Conception validée, maquettes des écrans |
| 1er novembre 2026 | Interface et API |
| 2 novembre 2026 | Mise en ligne |
| 3 novembre 2026 | Évaluation sur cas indépendants |
| 4 novembre 2026 | Rapport technique et guide de vérification |
| 5 novembre 2026 | Livraison |

## 10. Risques

| Risque | Impact | Mesure |
|---|---|---|
| Interprétation erronée d'une clause par le modèle | Verdict faux | Vérification des citations ; verdict déduit des contrôles ; cas indéterminés explicites |
| Découpage incorrect d'un nouveau contrat | Clause manquante | Rapport d'import contrôlé à chaque ajout |
| Temps de réponse élevé sans GPU | Adoption | Affichage immédiat des clauses ; verdict en second temps |
| Données d'entraînement synthétiques | Performance réelle inconnue | Test sur cas indépendants ; réentraînement prévu sur données réelles |
| Mise en ligne sur infrastructure gratuite | Disponibilité | Image reproductible ; journal de déploiement |

## 11. Hypothèses

- Les conditions particulières sont disponibles sous forme structurée.
- Le catalogue des garanties de chaque contrat est validé par un expert métier avant mise en service.
- L'outil est utilisé par des gestionnaires formés, qui conservent la décision.
