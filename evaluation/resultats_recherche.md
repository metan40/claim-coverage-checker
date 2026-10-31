# Évaluation de la recherche des clauses

Contexte transmis au LLM : 16 clauses au plus (5 garanties/conditions, 5 exclusions, 4 définitions).

| Configuration | Rappel global | Vélo | Bougie | Exclusions décisives |
|---|---|---|---|---|
| complet | 12/14 | 7/8 | 5/6 | 4/4 |
| sans synonymes | 7/14 | 7/8 | 0/6 | 3/4 |
| sans familles du classifieur | 10/14 | 5/8 | 5/6 | 4/4 |
| sans quotas (BM25 seul) | 11/14 | 5/8 | 6/6 | 4/4 |

## Détail (configuration complète)

| Cas | Contrat | Clause attendue | Rôle | Trouvée |
|---|---|---|---|---|
| velo | sogessur_fr | « locaux à usage commun des occupants » | exclusion décisive | oui |
| velo | sogessur_fr | « non attachés à un point fixe » | exclusion décisive | oui |
| velo | sogessur_fr | « formule Initiale avec option Vol » | garantie souscrite ? | oui |
| velo | ethias_be | « se trouvant dans les parties communes » | exclusion décisive | oui |
| velo | ethias_be | « uniquement si mention en est faite » | garantie optionnelle | oui |
| velo | baloise_lu | « point d’attache fixé au sol » | condition | **non** |
| velo | baloise_lu | « portes d’accès doivent être fermées à clé » | condition | oui |
| velo | baloise_lu | « Vélos et vélos à assistance électrique » | définition | oui |
| bougie | sogessur_fr | « fers à repasser et appareils de chauffage » | exclusion décisive | oui |
| bougie | ethias_be | « La combustion sans flamme » | garantie | oui |
| bougie | ethias_be | « flammes évoluant en dehors d’un foyer normal » | définition | oui |
| bougie | baloise_lu | « Détériorations ou brûlures causés au linge » | définition décisive | oui |
| bougie | baloise_lu | « action subite de la chaleur » | garantie | oui |
| bougie | baloise_lu | « du mobilier de jardin » | définition | **non** |

Familles prédites pour « velo » : vol, evenements_naturels

Familles prédites pour « bougie » : incendie
