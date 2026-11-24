# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : evaluation/experience_lsa.py
# Auteur  : Thierry MBARGA
# Rôle    : Expérience : l'analyse sémantique latente (SVD) améliore-t-elle
#           la recherche ?
# Lancer  : python evaluation/experience_lsa.py
# ---------------------------------------------------------------------------
"""Expérience : l'analyse sémantique latente (SVD) améliore-t-elle la recherche ?

On compare, sur les clauses décisives des deux cas du sujet
(`clauses_attendues.csv`), le rappel dans les 16 premières clauses de :
- BM25 seul (index FTS5 de la base) ;
- LSA seule : TF-IDF (racines, mots vides retirés) réduit par SVD tronquée,
  requête projetée dans l'espace latent, similarité cosinus ;
- la fusion des deux classements par RRF.

Usage : ``python evaluation/experience_lsa.py``
"""
import csv
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.database import DB_PATH, normalize  # noqa: E402
from src.retrieval import STOP_WORDS, _candidates, fts_query, query_terms, stem  # noqa: E402

HERE = Path(__file__).resolve().parent
TOP = 16
CASES = {
    "velo": "Je me fais voler mon vélo dans le local commun de l'immeuble, qui n'était pas fermé à clé.",
    "bougie": "Un assuré laisse une bougie sur la table de son jardin pendant ses vacances. "
              "Avec la chaleur, la bougie fond et abîme la table.",
}


def analyzer(text):
    return [stem(w) for w in re.findall(r"[a-z]+", normalize(text)) if w not in STOP_WORDS and len(w) > 2]


def main():
    connection = sqlite3.connect(DB_PATH)
    rows = connection.execute("SELECT a.id, c.code, a.texte, a.section FROM articles a "
                              "JOIN contrats c ON c.id = a.contrat_id").fetchall()
    ids = [r[0] for r in rows]
    codes = np.array([r[1] for r in rows])
    by_id = {r[0]: (r[2], r[3]) for r in rows}
    vectorizer = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True, min_df=2)
    X = vectorizer.fit_transform([r[3] + " " + r[2] for r in rows])
    print(f"Matrice clauses × termes : {X.shape[0]} × {X.shape[1]}, "
          f"densité {100 * X.nnz / (X.shape[0] * X.shape[1]):.2f} %")
    with (HERE / "clauses_attendues.csv").open(encoding="utf-8") as handle:
        expected = list(csv.DictReader(handle))

    def found(clause_ids, row):
        return any(row["fragment"] in by_id[i][0] and row["section_contient"] in by_id[i][1]
                   for i in clause_ids)

    for k in (50, 100, 200):
        svd = TruncatedSVD(n_components=k, random_state=0)
        Z = svd.fit_transform(X)
        Z /= np.linalg.norm(Z, axis=1, keepdims=True).clip(1e-9)
        scores = {"BM25": 0, "LSA": 0, "BM25 + LSA (RRF)": 0}
        for row in expected:
            description = CASES[row["cas"]]
            q = svd.transform(vectorizer.transform([description + " " + " ".join(query_terms(description))]))[0]
            q /= np.linalg.norm(q)
            similarity = Z @ q
            similarity[codes != row["contrat"]] = -9
            lsa = [ids[i] for i in np.argsort(-similarity)[:80]]
            bm25 = [c.id for c in _candidates(connection, row["contrat"], fts_query(query_terms(description)))]
            fused = {}
            for ranking in (bm25, lsa):
                for rank, clause_id in enumerate(ranking):
                    fused[clause_id] = fused.get(clause_id, 0) + 1 / (60 + rank + 1)
            hybrid = sorted(fused, key=lambda i: -fused[i])
            scores["BM25"] += found(bm25[:TOP], row)
            scores["LSA"] += found(lsa[:TOP], row)
            scores["BM25 + LSA (RRF)"] += found(hybrid[:TOP], row)
        summary = ", ".join(f"{name} {value}/{len(expected)}" for name, value in scores.items())
        print(f"k = {k} (variance expliquée {svd.explained_variance_ratio_.sum():.0%}) : {summary}")


if __name__ == "__main__":
    main()
