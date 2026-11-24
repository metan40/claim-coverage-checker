# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : evaluation/experience_svd_visualisation.py
# Auteur  : Thierry MBARGA
# Rôle    : Expérience : réduire la matrice TF-IDF par SVD pour visualiser
#           et regrouper
# Lancer  : python evaluation/experience_svd_visualisation.py
# ---------------------------------------------------------------------------
"""Expérience : réduire la matrice TF-IDF par SVD pour visualiser et regrouper.

1. Descriptions de sinistres (entraînement généré et test écrit à la main)
   projetées en 2D ; regroupement k-means (k = 6) dans un espace SVD de
   dimension 50, comparé aux vraies familles (indice de Rand ajusté, ARI).
2. Clauses des trois contrats projetées en 2D ; regroupement k-means comparé
   aux familles de garanties et aux contrats.

Usage : ``python evaluation/experience_svd_visualisation.py``
(figures dans ``evaluation/figures/``).
"""
import re
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.decomposition import TruncatedSVD  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.metrics import adjusted_rand_score  # noqa: E402
from sklearn.preprocessing import normalize as l2_normalize  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.classifier import FAMILIES, TEST_PATH, TRAIN_PATH, load  # noqa: E402
from src.database import DB_PATH, normalize  # noqa: E402
from src.retrieval import STOP_WORDS, stem  # noqa: E402

FIGURES = Path(__file__).resolve().parent / "figures"
COLORS = dict(zip(FAMILIES, ["#1F4E79", "#B45309", "#0F766E", "#7C3AED", "#64748B", "#BE185D"]))


def analyzer(text):
    return [stem(w) for w in re.findall(r"[a-z]+", normalize(text)) if w not in STOP_WORDS and len(w) > 2]


def claims():
    train_x, train_y = load(TRAIN_PATH)
    test_x, test_y = load(TEST_PATH)
    X = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True).fit_transform(train_x + test_x)
    svd2 = TruncatedSVD(2, random_state=0)
    Z = svd2.fit_transform(X)
    Z50 = l2_normalize(TruncatedSVD(50, random_state=0).fit_transform(X))
    kmeans = KMeans(6, n_init=10, random_state=0).fit(Z50[:len(train_x)])
    print(f"Sinistres : variance conservée en 2D {svd2.explained_variance_ratio_.sum():.1%} ; "
          f"ARI k-means/familles {adjusted_rand_score(train_y, kmeans.labels_):.2f} (entraînement), "
          f"{adjusted_rand_score(test_y, kmeans.predict(Z50[len(train_x):])):.2f} (test)")
    fig, ax = plt.subplots(figsize=(7, 5))
    for family in FAMILIES:
        idx = [i for i, y in enumerate(train_y) if y == family]
        ax.scatter(Z[idx, 0], Z[idx, 1], s=8, alpha=0.35, c=COLORS[family], label=family)
        idx = [len(train_x) + i for i, y in enumerate(test_y) if y == family]
        ax.scatter(Z[idx, 0], Z[idx, 1], s=40, marker="^", edgecolor="k", linewidth=0.5, c=COLORS[family])
    ax.set_title("Descriptions de sinistres projetées en 2D par SVD\n"
                 "(points : entraînement généré ; triangles : test écrit à la main)", fontsize=10)
    ax.set_xlabel("composante 1")
    ax.set_ylabel("composante 2")
    ax.legend(fontsize=7, markerscale=2)
    fig.tight_layout()
    fig.savefig(FIGURES / "svd_sinistres_2d.png", dpi=130)


def clauses():
    connection = sqlite3.connect(DB_PATH)
    rows = connection.execute(
        "SELECT c.code, a.section || ' ' || a.texte, "
        "(SELECT group_concat(famille) FROM article_familles WHERE article_id = a.id) "
        "FROM articles a JOIN contrats c ON c.id = a.contrat_id").fetchall()
    X = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True, min_df=2).fit_transform([r[1] for r in rows])
    Z = TruncatedSVD(2, random_state=0).fit_transform(X)
    Z100 = l2_normalize(TruncatedSVD(100, random_state=0).fit_transform(X))
    family = [(r[2] or "").split(",")[0] for r in rows]
    with_family = [i for i, f in enumerate(family) if f]
    labels = KMeans(8, n_init=10, random_state=0).fit(Z100).labels_
    by_contract = KMeans(3, n_init=10, random_state=0).fit(Z100).labels_
    print(f"Clauses : ARI k-means/famille {adjusted_rand_score([family[i] for i in with_family], labels[with_family]):.2f} ; "
          f"ARI k-means/contrat {adjusted_rand_score([r[0] for r in rows], by_contract):.2f}")
    fig, ax = plt.subplots(figsize=(7, 5))
    for code, color in {"baloise_lu": "#1F4E79", "ethias_be": "#B45309", "sogessur_fr": "#0F766E"}.items():
        idx = [i for i, r in enumerate(rows) if r[0] == code]
        ax.scatter(Z[idx, 0], Z[idx, 1], s=8, alpha=0.5, c=color, label=code)
    ax.set_title("Clauses des trois contrats projetées en 2D par SVD", fontsize=10)
    ax.set_xlabel("composante 1")
    ax.set_ylabel("composante 2")
    ax.legend(fontsize=8, markerscale=2)
    fig.tight_layout()
    fig.savefig(FIGURES / "svd_clauses_2d.png", dpi=130)


if __name__ == "__main__":
    FIGURES.mkdir(exist_ok=True)
    claims()
    clauses()
