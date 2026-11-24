# Auteur : Thierry MBARGA
"""Évaluation de bout en bout de l'instruction d'un sinistre (7 contrôles).

Jeu : ``evaluation/cas_couverture.csv``. Chaque ligne est un jugement (cas i,
contrat j) : la police utilisée, le verdict attendu, les verdicts acceptés et
un fragment de la clause décisive, retrouvé mot pour mot dans les conditions
générales. Le partage dev / test est écrit dans le fichier avant toute mesure.

Chaque sinistre est inséré dans une copie en mémoire de la base, puis instruit
exactement comme dans l'application : classifieur -> contrôles factuels ->
contrôles d'interprétation (modèle de langage) -> verdict.

Mesures, pour chaque jugement et chaque passage :

* verdict exact : égal au verdict attendu ;
* verdict acceptable : dans les verdicts acceptés (« indéterminé » est accepté
  quand il est prudent sans être faux) ;
* fausse couverture : « potentiellement couvert » pour un cas non couvert
  (l'erreur la plus coûteuse) ;
* faux refus : « potentiellement exclu » pour un cas couvert ;
* clause décisive transmise au modèle (recherche des clauses).

Référence : sans modèle (``--sans-modele``), les contrôles 4 à 6 restent « à
vérifier » ; toute amélioration se mesure contre cette référence.

Proportions avec intervalle de Wilson à 95 %. Les passages répétés d'un même
jugement ne sont pas indépendants : les intervalles sont légèrement optimistes.

Usage :
    python evaluation/evaluer_instruction.py --sans-modele
    python evaluation/evaluer_instruction.py --repetitions 2 --sortie enregistrements.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.classifier import load_model, predict  # noqa: E402
from src.database import DB_PATH, normalize  # noqa: E402
from src.decision import OLLAMA_MODEL, call_ollama  # noqa: E402
from src.instruction import instruire  # noqa: E402
from src.retrieval import retrieve  # noqa: E402

CASES = ROOT / "evaluation" / "cas_couverture.csv"
SURVENANCE, CONNAISSANCE, DECLARATION = "2026-09-11", "2026-09-11", "2026-09-14"


def wilson(k: int, n: int, z: float = 1.96) -> str:
    if n == 0:
        return "n = 0"
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{k}/{n} = {p:.0%} [{max(0, centre - half):.0%} ; {min(1, centre + half):.0%}]"


def contains(fragment: str, text: str) -> bool:
    return bool(fragment) and normalize(fragment) in normalize(text)


def memory_copy(path: Path = DB_PATH) -> sqlite3.Connection:
    """Copie en mémoire : la base livrée n'est jamais modifiée."""
    source = sqlite3.connect(path)
    copy = sqlite3.connect(":memory:")
    source.backup(copy)
    source.close()
    return copy


def insert_claims(connection: sqlite3.Connection, rows: list[dict]) -> None:
    for number, row in enumerate(rows, start=1):
        row["id"] = f"EVAL-{number:03d}"
        connection.execute(
            "INSERT INTO sinistres (id, numero_police, date_survenance, date_connaissance,"
            " date_declaration, description, bien, montant_estime) VALUES (?,?,?,?,?,?,?,?)",
            (row["id"], row["police"], SURVENANCE, CONNAISSANCE, DECLARATION,
             row["description"], row["bien"] or None, float(row["montant_estime"])))
    connection.commit()


def evaluate_row(connection: sqlite3.Connection, model, row: dict, llm) -> dict:
    familles = predict(model, row["description"]).families
    instruction = instruire(connection, row["id"], familles, llm)
    connection.row_factory = None
    clauses = retrieve(connection, row["contrat"], row["description"], familles)
    acceptes = row["verdicts_acceptes"].split("|")
    fragment = row["fragment_decisif"]
    return {
        "cas": row["cas"], "partie": row["partie"], "categorie": row["categorie"],
        "contrat": row["contrat"], "police": row["police"],
        "verdict_attendu": row["verdict_attendu"], "acceptes": acceptes,
        "verdict": instruction.verdict, "nature": instruction.nature,
        "exact": instruction.verdict == row["verdict_attendu"],
        "acceptable": instruction.verdict in acceptes,
        "fausse_couverture": instruction.verdict == "potentiellement_couvert"
        and "potentiellement_couvert" not in acceptes,
        "faux_refus": instruction.verdict == "potentiellement_exclu"
        and row["verdict_attendu"] == "potentiellement_couvert",
        "clause_decisive_transmise": None if not fragment else any(
            contains(fragment, c.section + " " + c.text) for c in clauses),
        "familles": familles,
        "controles": [{"numero": c.numero, "statut": c.statut, "constat": c.constat}
                      for c in instruction.controles],
    }


def report(records: list[dict], modele: str) -> str:
    lines = ["# Évaluation de bout en bout de l'instruction\n",
             f"Modèle : `{modele}` ; {len(records)} jugements × passages.\n"]
    for partie in ("dev", "test"):
        rs = [r for r in records if r["partie"] == partie]
        if not rs:
            continue
        couverts = [r for r in rs if r["verdict_attendu"] == "potentiellement_couvert"]
        non_couverts = [r for r in rs if "potentiellement_couvert" not in r["acceptes"]]
        avec_fragment = [r for r in rs if r["clause_decisive_transmise"] is not None]
        lines += [f"\n## {partie.capitalize()}\n", "| Mesure | Résultat |", "|---|---|",
                  f"| Verdict exact | {wilson(sum(r['exact'] for r in rs), len(rs))} |",
                  f"| Verdict acceptable | {wilson(sum(r['acceptable'] for r in rs), len(rs))} |",
                  f"| Fausse couverture (cas non couverts) | "
                  f"{wilson(sum(r['fausse_couverture'] for r in non_couverts), len(non_couverts))} |",
                  f"| Faux refus (cas couverts) | {wilson(sum(r['faux_refus'] for r in couverts), len(couverts))} |",
                  f"| Clause décisive transmise au modèle | "
                  f"{wilson(sum(bool(r['clause_decisive_transmise']) for r in avec_fragment), len(avec_fragment))} |",
                  "", "| Catégorie | Verdict exact | Verdict acceptable |", "|---|---|---|"]
        groupes = defaultdict(list)
        for r in rs:
            groupes[r["categorie"]].append(r)
        for categorie, g in sorted(groupes.items()):
            lines.append(f"| {categorie} | {wilson(sum(r['exact'] for r in g), len(g))} | "
                         f"{wilson(sum(r['acceptable'] for r in g), len(g))} |")
    lines += ["\n## Détail\n", "| Partie | Cas | Contrat | Attendu | Obtenu | Exact | Clause transmise | Contrôles 3-6 |",
              "|---|---|---|---|---|---|---|---|"]
    for r in records:
        etats = " ".join(f"{c['numero']}:{c['statut']}" for c in r["controles"] if 3 <= c["numero"] <= 6)
        lines.append(f"| {r['partie']} | {r['cas']} | {r['contrat']} | {r['verdict_attendu']} | {r['verdict']} | "
                     f"{'oui' if r['exact'] else '**non**'} | {r['clause_decisive_transmise']} | {etats} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--sans-modele", action="store_true", help="référence : contrôles 4 à 6 sans modèle")
    parser.add_argument("--sortie", default="", help="fichier JSONL des enregistrements")
    parser.add_argument("--rapport", default=str(ROOT / "evaluation" / "resultats_instruction.md"))
    args = parser.parse_args()

    llm = None if args.sans_modele else call_ollama
    modele = "aucun (référence)" if args.sans_modele else OLLAMA_MODEL
    rows = list(csv.DictReader(CASES.open(encoding="utf-8")))
    connection = memory_copy()
    insert_claims(connection, rows)
    model = load_model()
    records = []
    for passage in range(1, args.repetitions + 1):
        for number, row in enumerate(rows, start=1):
            record = evaluate_row(connection, model, row, llm)
            record["passage"] = passage
            records.append(record)
            print(f"[{passage}.{number}/{len(rows)}] {row['partie']:<4} {row['cas']:<20} {row['contrat']:<12} "
                  f"attendu={row['verdict_attendu']:<24} obtenu={record['verdict']:<24} "
                  f"{'OK' if record['exact'] else 'NON'}", flush=True)
            if args.sortie:
                with open(args.sortie, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    texte = report(records, modele)
    Path(args.rapport).write_text(texte, encoding="utf-8")
    print(texte)


if __name__ == "__main__":
    main()
