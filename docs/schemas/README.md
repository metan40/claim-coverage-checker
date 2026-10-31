# Schémas

Chaque schéma existe en trois formes : la source modifiable, une image
vectorielle (SVG) et une image (PNG). Les cadres en pointillés signalent les
éléments prévus, pas encore réalisés.

| Schéma | Ce qu'il montre | Source |
|---|---|---|
| `instruction_sinistre` | Le processus métier : de la déclaration à la décision, en trois couloirs (assuré, gestionnaire, outil) | BPMN 2.0 (`.bpmn`), généré par `generer_bpmn.py` |
| `architecture` | Les composants : préparation hors ligne des contrats, base de données, application, modèle de langage local | Mermaid (`.mmd`) |
| `modele_donnees` | Les tables et leurs relations, des conditions générales jusqu'aux contrôles d'une analyse | Mermaid (`.mmd`) |
| `sequence_analyse` | L'ordre des échanges lors de l'instruction d'un sinistre ; les contrôles factuels avant le modèle de langage | Mermaid (`.mmd`) |
| `import_contrat` | L'ajout d'une nouvelle version de conditions générales, avec ses deux contrôles humains | Mermaid (`.mmd`) |
| `cas_utilisation` | Les acteurs et ce que chacun fait avec l'outil | Mermaid (`.mmd`) |

## Ouvrir et modifier

- **Bizagi Modeler, Enterprise Architect** : importer `instruction_sinistre.bpmn` (BPMN 2.0 XML, avec la disposition graphique).
- **Visio, PowerPoint, Word** : insérer le fichier `.svg`, puis « Convertir en forme » ou « Dissocier » pour obtenir des formes modifiables.
- **Sources Mermaid** : modifiables dans tout éditeur de texte ; aperçu dans VS Code (extension Mermaid) ou sur mermaid.live.

## Régénérer les images

```bash
python docs/schemas/generer_bpmn.py
cd docs/schemas
for f in architecture modele_donnees sequence_analyse import_contrat cas_utilisation; do
  mmdc -i $f.mmd -o $f.svg -c theme.json -b white
  mmdc -i $f.mmd -o $f.png -c theme.json -b white -s 2
done
```

`mmdc` est fourni par le paquet npm `@mermaid-js/mermaid-cli`.
