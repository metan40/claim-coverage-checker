# Évaluation de bout en bout de l'instruction

Modèle : `aucun (référence)` ; 39 jugements × passages.


## Dev

| Mesure | Résultat |
|---|---|
| Verdict exact | 7/18 = 39% [20% ; 61%] |
| Verdict acceptable | 18/18 = 100% [82% ; 100%] |
| Fausse couverture (cas non couverts) | 0/9 = 0% [0% ; 30%] |
| Faux refus (cas couverts) | 0/9 = 0% [0% ; 30%] |
| Clause décisive transmise au modèle | 10/12 = 83% [55% ; 95%] |

| Catégorie | Verdict exact | Verdict acceptable |
|---|---|---|
| couvert_base | 0/9 = 0% [0% ; 30%] | 9/9 = 100% [70% ; 100%] |
| exclusion | 1/3 = 33% [6% ; 79%] | 3/3 = 100% [44% ; 100%] |
| hors_contrat | 6/6 = 100% [61% ; 100%] | 6/6 = 100% [61% ; 100%] |

## Test

| Mesure | Résultat |
|---|---|
| Verdict exact | 6/21 = 29% [14% ; 50%] |
| Verdict acceptable | 18/21 = 86% [65% ; 95%] |
| Fausse couverture (cas non couverts) | 0/15 = 0% [0% ; 20%] |
| Faux refus (cas couverts) | 0/6 = 0% [0% ; 39%] |
| Clause décisive transmise au modèle | 12/18 = 67% [44% ; 84%] |

| Catégorie | Verdict exact | Verdict acceptable |
|---|---|---|
| couvert_base | 0/6 = 0% [0% ; 39%] | 6/6 = 100% [61% ; 100%] |
| exclusion | 0/3 = 0% [0% ; 56%] | 0/3 = 0% [0% ; 56%] |
| hors_contrat | 3/6 = 50% [19% ; 81%] | 6/6 = 100% [61% ; 100%] |
| officielle | 3/6 = 50% [19% ; 81%] | 6/6 = 100% [61% ; 100%] |

## Détail

| Partie | Cas | Contrat | Attendu | Obtenu | Exact | Clause transmise | Contrôles 3-6 |
|---|---|---|---|---|---|---|---|
| dev | incendie_cuisine | baloise_lu | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | incendie_cuisine | ethias_be | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | incendie_cuisine | sogessur_fr | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:satisfait 6:a_verifier 6:satisfait |
| test | foudre_toiture | baloise_lu | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | foudre_toiture | ethias_be | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | foudre_toiture | sogessur_fr | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | fuite_lave_linge | baloise_lu | potentiellement_couvert | indetermine | **non** | True | 3:a_verifier 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | fuite_lave_linge | ethias_be | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | fuite_lave_linge | sogessur_fr | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | tempete_tuiles | baloise_lu | potentiellement_couvert | indetermine | **non** | True | 3:a_verifier 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | tempete_tuiles | ethias_be | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | tempete_tuiles | sogessur_fr | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | fumee_suie | baloise_lu | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | fumee_suie | ethias_be | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:satisfait 6:a_verifier 6:satisfait |
| dev | fumee_suie | sogessur_fr | potentiellement_couvert | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | incendie_volontaire | baloise_lu | potentiellement_exclu | indetermine | **non** | False | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | incendie_volontaire | ethias_be | potentiellement_exclu | indetermine | **non** | False | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | incendie_volontaire | sogessur_fr | potentiellement_exclu | indetermine | **non** | False | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | panne_usure | baloise_lu | potentiellement_exclu | indetermine | **non** | False | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | panne_usure | ethias_be | indetermine | indetermine | oui | False | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | panne_usure | sogessur_fr | potentiellement_exclu | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | pare_brise | baloise_lu | potentiellement_exclu | indetermine | **non** | False | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | pare_brise | ethias_be | potentiellement_exclu | indetermine | **non** | False | 3:satisfait 4:a_verifier 5:satisfait 6:a_verifier 6:satisfait |
| test | pare_brise | sogessur_fr | potentiellement_exclu | indetermine | **non** | False | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | deces_carence | baloise_lu | indetermine | indetermine | oui | None | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | deces_carence | ethias_be | indetermine | indetermine | oui | None | 3:satisfait 4:a_verifier 5:satisfait 6:a_verifier 6:satisfait |
| dev | deces_carence | sogessur_fr | indetermine | indetermine | oui | None | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | annulation_voyage | baloise_lu | indetermine | indetermine | oui | None | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | annulation_voyage | ethias_be | indetermine | indetermine | oui | None | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | annulation_voyage | sogessur_fr | indetermine | indetermine | oui | None | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | frais_hopital_ski | baloise_lu | indetermine | indetermine | oui | None | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | frais_hopital_ski | ethias_be | indetermine | indetermine | oui | None | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| dev | frais_hopital_ski | sogessur_fr | indetermine | indetermine | oui | None | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | velo_local_commun | baloise_lu | indetermine | indetermine | oui | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | velo_local_commun | ethias_be | potentiellement_exclu | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | velo_local_commun | sogessur_fr | potentiellement_exclu | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | bougie_table | baloise_lu | indetermine | indetermine | oui | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | bougie_table | ethias_be | indetermine | indetermine | oui | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
| test | bougie_table | sogessur_fr | potentiellement_exclu | indetermine | **non** | True | 3:satisfait 4:a_verifier 5:a_verifier 6:a_verifier 6:satisfait |
