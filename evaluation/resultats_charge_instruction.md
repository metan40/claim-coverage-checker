# Test de charge — contrôles factuels

- Portefeuille : 100 000 polices synthétiques, 54 452 options (chargement 0.8 s) ; base de 17 Mo.
- 1000 déclarations instruites (contrôles 1, 2, 3, délai, montant).
- Durée par sinistre : médiane 0.11 ms, 95e centile 0.19 ms, maximum 0.93 ms.

| Verdict après contrôles factuels | Sinistres |
|---|---|
| indetermine | 613 |
| potentiellement_exclu | 387 |

| Contrôle bloquant | Sinistres |
|---|---|
| 3. Garantie souscrite | 300 |
| 1. Contrat en vigueur | 107 |
| 7. Montant | 22 |

Les contrôles 4, 5 et 6 (interprétation des clauses) restent « à vérifier » : sans contrôle bloquant, le verdict est donc « indéterminé » à ce stade.
