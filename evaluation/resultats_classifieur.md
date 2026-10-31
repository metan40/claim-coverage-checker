# Comparaison des classifieurs de sinistres

Entraînement : 780 descriptions générées. Test : 60 descriptions écrites à la main.

| Modèle | F1 macro (validation croisée) | Exactitude test | F1 macro test | Top-2 test | Log-loss test | Brier test |
|---|---|---|---|---|---|---|
| naive_bayes_mots | 1.000 ± 0.000 | 0.833 | 0.827 | 0.917 | 0.652 | 0.293 |
| reglog_mots | 1.000 ± 0.000 | 0.833 | 0.828 | 0.950 | 0.579 | 0.271 |
| reglog_mots_caracteres | 1.000 ± 0.000 | 0.900 | 0.893 | 0.950 | 0.437 | 0.199 |
| svm_mots_caracteres_calibre | 1.000 ± 0.000 | 0.900 | 0.893 | 0.950 | 0.350 | 0.164 |

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

Règle « deuxième famille si probabilité < 0.6 » : la bonne famille est retenue dans 95% des cas, avec deux familles retenues dans 37% des cas.

## Erreurs du modèle retenu

| Id | Description | Vraie | Prédite (probabilité) | Mots décisifs |
|---|---|---|---|---|
| T003 | En rentrant du travail j'ai trouvé l'appartement sens dessus dessous et il manque le portable et la console. | vol | degats_des_eaux (0.38) | et, dessus, appartement, le |
| T006 | Ma voisine a vu deux hommes repartir avec notre barbecue et nos chaises longues. | vol | incendie (0.31) | barbecue, mmes, mmes , epa |
| T010 | Le cadenas du box a été sectionné et la moto-cross de mon fils n'est plus là. | vol | responsabilite_civile (0.45) | fils, mon fils, de mon, mon |
| T027 | La douche à l'italienne n'est plus étanche : le salon en dessous est taché. | degats_des_eaux | bris_de_glace (0.50) | est, douche, salon, le salon |
| T041 | Les bourrasques de la nuit ont fait tomber une partie de la cheminée sur la voiture. | evenements_naturels | incendie (0.59) | sur la, les, cheminee, la cheminee |
| T042 | Des grêlons gros comme des balles de golf ont troué les panneaux solaires. | evenements_naturels | vol (0.43) | des, ont, ol,  o |

## Cas du sujet

- T001 « Mon vélo, que je laisse dans le local commun de la résidence, n'y était plus ce matin. Le local n'était pas fermé à clé. » → retenues : vol, evenements_naturels (vol 0.47, evenements_naturels 0.17, degats_des_eaux 0.12)
- T002 « Pendant nos vacances, une bougie restée allumée sur la terrasse a fait fondre notre table de jardin. » → retenues : incendie (incendie 0.97, evenements_naturels 0.02, responsabilite_civile 0.00)
