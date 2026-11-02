# Comparaison des classifieurs de sinistres

Entraînement : 780 descriptions générées. Test : 60 descriptions écrites à la main.

| Modèle | F1 macro (validation croisée) | Exactitude test | F1 macro test | Top-2 test | Log-loss test | Brier test |
|---|---|---|---|---|---|---|
| naive_bayes_mots | 1.000 ± 0.000 | 0.833 | 0.827 | 0.917 | 0.645 | 0.290 |
| reglog_mots | 1.000 ± 0.000 | 0.833 | 0.828 | 0.950 | 0.560 | 0.260 |
| reglog_mots_caracteres | 1.000 ± 0.000 | 0.900 | 0.893 | 0.950 | 0.422 | 0.191 |
| svm_mots_caracteres_calibre | 1.000 ± 0.000 | 0.900 | 0.893 | 0.967 | 0.335 | 0.156 |

## Comparaison appariée avec `reglog_mots_caracteres` (test de McNemar exact)

| Modèle | Juste seul | Retenu juste seul | p-value |
|---|---|---|---|
| naive_bayes_mots | 1 | 5 | 0.22 |
| reglog_mots | 1 | 5 | 0.22 |
| svm_mots_caracteres_calibre | 0 | 0 | 1.00 |

Une p-value élevée signifie que l'écart observé peut être dû au hasard sur 60 cas.

## Modèle retenu : `reglog_mots_caracteres`

Matrice de confusion sur le test (lignes : vraie famille ; colonnes : prédite) :

| | vol | inc | eau | bdg | nat | rc |
|---|---|---|---|---|---|---|
| vol | 6 | 1 | 1 | 0 | 0 | 1 |
| inc | 0 | 11 | 0 | 0 | 0 | 0 |
| eau | 0 | 0 | 9 | 1 | 0 | 0 |
| bdg | 0 | 0 | 0 | 10 | 0 | 0 |
| nat | 1 | 1 | 0 | 0 | 8 | 0 |
| rc | 0 | 0 | 0 | 0 | 0 | 10 |

Règle « deuxième famille si probabilité < 0.6 » : la bonne famille est retenue dans 95% des cas, avec deux familles retenues dans 35% des cas.

## Erreurs du modèle retenu

| Id | Description | Vraie | Prédite (probabilité) | Mots décisifs |
|---|---|---|---|---|
| T003 | En rentrant du travail j'ai trouvé l'appartement sens dessus dessous et il manque le portable et la console. | vol | degats_des_eaux (0.39) | et, dessus, appartement, et  |
| T006 | Ma voisine a vu deux hommes repartir avec notre barbecue et nos chaises longues. | vol | incendie (0.29) | barbecue, mmes, mmes , epa |
| T010 | Le cadenas du box a été sectionné et la moto-cross de mon fils n'est plus là. | vol | responsabilite_civile (0.45) | fils, mon fils, de mon, mon |
| T027 | La douche à l'italienne n'est plus étanche : le salon en dessous est taché. | degats_des_eaux | bris_de_glace (0.52) | est, douche, salon, le salon |
| T041 | Les bourrasques de la nuit ont fait tomber une partie de la cheminée sur la voiture. | evenements_naturels | incendie (0.51) | sur la, les, sur, cheminee |
| T042 | Des grêlons gros comme des balles de golf ont troué les panneaux solaires. | evenements_naturels | vol (0.44) | des, ont, ol,  o |

## Cas du sujet

- T001 « Je me fais voler mon vélo dans le local commun de l'immeuble, qui n'était pas fermé à clé. » → retenues : vol (vol 0.95, responsabilite_civile 0.01, evenements_naturels 0.01)
- T002 « Un assuré laisse une bougie sur la table de son jardin pendant ses vacances. Avec la chaleur, la bougie fond et abîme la table. » → retenues : incendie (incendie 0.85, responsabilite_civile 0.05, evenements_naturels 0.04)
