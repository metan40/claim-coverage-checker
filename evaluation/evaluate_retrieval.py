# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : evaluation/evaluate_retrieval.py
# Auteur  : Thierry MBARGA
# Rôle    : Évaluation de la recherche des clauses sur les deux cas du sujet
# Lancer  : python evaluation/evaluate_retrieval.py
# ---------------------------------------------------------------------------
"""Évaluation de la recherche des clauses sur les deux cas du sujet.

Pour chaque cas et chaque contrat, on vérifie que les clauses décisives
(``clauses_attendues.csv``, repérées par un fragment de leur texte) figurent
dans le contexte transmis au LLM. Mesure : rappel = clauses attendues
trouvées / clauses attendues.

Ablations : on retire une brique à la fois pour mesurer son apport.

Usage : ``python evaluation/evaluate_retrieval.py``
"""
import csv
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.classifier import load_model, predict  # noqa: E402
from src.database import DB_PATH  # noqa: E402
from src.retrieval import QUOTAS, retrieve  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "resultats_recherche.md"
# Les deux cas de l'énoncé, mot pour mot.
CASES = {
    "velo": "Je me fais voler mon vélo dans le local commun de l'immeuble, qui n'était pas "
            "fermé à clé.",
    "bougie": "Un assuré laisse une bougie sur la table de son jardin pendant ses vacances. "
              "Avec la chaleur, la bougie fond et abîme la table.",
}
TOTAL = sum(QUOTAS.values())
CONFIGURATIONS = {
    "complet": {},
    "sans synonymes": {"use_synonyms": False},
    "sans familles du classifieur": {"use_families": False},
    "sans quotas (BM25 seul)": {"quotas": {},
                                 "_no_quota": True},
}


def expected_rows():
    with (HERE / "clauses_attendues.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def found(clauses, row) -> bool:
    return any(row["fragment"] in c.text and row["section_contient"] in c.section for c in clauses)


def run(connection, model, options):
    options = dict(options)
    no_quota = options.pop("_no_quota", False)
    results = []
    for row in expected_rows():
        description = CASES[row["cas"]]
        families = predict(model, description).families
        if no_quota:
            from src.retrieval import _candidates, fts_query, query_terms
            clauses = _candidates(connection, row["contrat"], fts_query(query_terms(description)))[:TOTAL]
        else:
            clauses = retrieve(connection, row["contrat"], description, families, **options)
        results.append((row, found(clauses, row)))
    return results


def main():
    connection = sqlite3.connect(DB_PATH)
    model = load_model()
    lines = ["# Évaluation de la recherche des clauses", "",
             f"Contexte transmis au LLM : {TOTAL} clauses au plus "
             f"({QUOTAS['garantie_condition']} garanties/conditions, {QUOTAS['exclusion']} exclusions, "
             f"{QUOTAS['definition']} définitions).", "",
             "| Configuration | Rappel global | Vélo | Bougie | Exclusions décisives |",
             "|---|---|---|---|---|"]
    details = None
    for name, options in CONFIGURATIONS.items():
        results = run(connection, model, options)
        if details is None:
            details = results

        def rate(selector):
            subset = [ok for row, ok in results if selector(row)]
            return f"{sum(subset)}/{len(subset)}"
        lines.append(f"| {name} | {rate(lambda r: True)} | {rate(lambda r: r['cas'] == 'velo')} | "
                     f"{rate(lambda r: r['cas'] == 'bougie')} | "
                     f"{rate(lambda r: 'exclusion décisive' in r['role'])} |")
    lines += ["", "## Détail (configuration complète)", "",
              "| Cas | Contrat | Clause attendue | Rôle | Trouvée |", "|---|---|---|---|---|"]
    for row, ok in details:
        lines.append(f"| {row['cas']} | {row['contrat']} | « {row['fragment']} » | {row['role']} | "
                     f"{'oui' if ok else '**non**'} |")
    for case, description in CASES.items():
        lines += ["", f"Familles prédites pour « {case} » : "
                  f"{', '.join(predict(model, description).families)}"]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
