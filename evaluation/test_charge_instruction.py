# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : evaluation/test_charge_instruction.py
# Auteur  : Thierry MBARGA
# Rôle    : Test de charge des contrôles factuels sur un portefeuille de
#           grande taille
# Lancer  : python evaluation/test_charge_instruction.py
# ---------------------------------------------------------------------------
"""Test de charge des contrôles factuels sur un portefeuille de grande taille.

Sur une copie de la base : ajout de 100 000 polices synthétiques et de
1 000 déclarations tirées au hasard, puis instruction factuelle de chacune
(contrôles 1, 2, 3, délai de déclaration et montant). On mesure la durée par
sinistre et la répartition des verdicts.

Usage : ``python evaluation/test_charge_instruction.py`` (écrit
``evaluation/resultats_charge_instruction.md``).
"""
import random
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.database import DB_PATH  # noqa: E402
from src.instruction import instruire  # noqa: E402
from src.portefeuille import ajouter  # noqa: E402

OUT = Path(__file__).with_name("resultats_charge_instruction.md")
POLICES, SINISTRES, SEED = 100_000, 1_000, 2026
CAS = [("vol", "velo", "Vol de vélo dans le local commun."),
       ("incendie", "mobilier_jardin", "Table de jardin abîmée par la chaleur."),
       ("degats_des_eaux", None, "Fuite d'eau sous l'évier.")]


def main() -> None:
    rng = random.Random(SEED)
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / "charge.sqlite"
        shutil.copy(DB_PATH, copy)
        start = time.perf_counter()
        n_polices, n_options = ajouter(POLICES, copy)
        load_time = time.perf_counter() - start
        connection = sqlite3.connect(copy)
        numeros = [r[0] for r in connection.execute("SELECT numero FROM polices WHERE origine = 'synthetique'")]
        rows = []
        for i in range(SINISTRES):
            famille, bien, texte = CAS[i % len(CAS)]
            survenance = date(2025, 6, 1) + timedelta(days=rng.randrange(480))
            declaration = survenance + timedelta(days=rng.choice([0, 1, 2, 3, 5, 9, 15]))
            rows.append((f"C-{i:05d}", rng.choice(numeros), survenance.isoformat(), None,
                         declaration.isoformat(), texte, bien, float(rng.randrange(100, 5000)), famille))
        connection.executemany("INSERT INTO sinistres VALUES (?,?,?,?,?,?,?,?)", [r[:8] for r in rows])
        connection.commit()
        durations, verdicts, blocking = [], Counter(), Counter()
        for row in rows:
            t0 = time.perf_counter()
            result = instruire(connection, row[0], [row[8]])
            durations.append((time.perf_counter() - t0) * 1000)
            verdicts[result.verdict] += 1
            for controle in result.controles:
                if controle.statut == "bloquant":
                    blocking[f"{controle.numero}. {controle.nom}"] += 1
        connection.close()
        size = copy.stat().st_size / 1e6

    durations.sort()
    lines = ["# Test de charge — contrôles factuels", "",
             f"- Portefeuille : {n_polices:_} polices synthétiques, {n_options:_} options "
             f"(chargement {load_time:.1f} s) ; base de {size:.0f} Mo.".replace("_", " "),
             f"- {SINISTRES} déclarations instruites (contrôles 1, 2, 3, délai, montant).",
             f"- Durée par sinistre : médiane {statistics.median(durations):.2f} ms, "
             f"95e centile {durations[int(0.95 * len(durations))]:.2f} ms, "
             f"maximum {durations[-1]:.2f} ms.", "",
             "| Verdict après contrôles factuels | Sinistres |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in verdicts.most_common()]
    lines += ["", "| Contrôle bloquant | Sinistres |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in blocking.most_common()]
    lines += ["", "Les contrôles 4, 5 et 6 (interprétation des clauses) restent « à vérifier » : "
              "sans contrôle bloquant, le verdict est donc « indéterminé » à ce stade."]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
