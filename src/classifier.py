"""Classification des descriptions de sinistres en familles de garanties.

Le modèle retenu est entraîné sur ``data/sinistres/sinistres_entrainement.csv``
(généré) et évalué sur ``data/sinistres/sinistres_test.csv`` (écrit à la
main, tournures différentes). La comparaison des algorithmes se trouve dans
``evaluation/evaluate_classifier.py``.

Usage : ``python -m src.classifier`` (entraîne et enregistre le modèle).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from src.database import normalize

ROOT = Path(__file__).resolve().parent.parent
TRAIN_PATH = ROOT / "data" / "sinistres" / "sinistres_entrainement.csv"
TEST_PATH = ROOT / "data" / "sinistres" / "sinistres_test.csv"
MODEL_PATH = ROOT / "models" / "classifieur_sinistres.joblib"

FAMILIES = ["vol", "incendie", "degats_des_eaux", "bris_de_glace",
            "evenements_naturels", "responsabilite_civile"]

# Si la probabilité la plus haute est sous ce seuil, on retient aussi la
# deuxième famille (le modèle hésite : mieux vaut chercher dans deux familles).
SECOND_FAMILY_THRESHOLD = 0.60
SEED = 2026


def load(path: Path) -> tuple[list[str], list[str]]:
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [row["description"] for row in rows], [row["famille"] for row in rows]


def _features(chars: bool = True) -> FeatureUnion | TfidfVectorizer:
    """Mots (1-2 grammes) et, en option, n-grammes de caractères (2-5) :
    ces derniers rapprochent « brûlé », « brûlure », « brûlée » et tolèrent
    les fautes de frappe."""
    words = TfidfVectorizer(preprocessor=normalize, ngram_range=(1, 2), min_df=1,
                            sublinear_tf=True)
    if not chars:
        return words
    characters = TfidfVectorizer(preprocessor=normalize, analyzer="char_wb",
                                 ngram_range=(2, 5), min_df=2, sublinear_tf=True)
    return FeatureUnion([("mots", words), ("caracteres", characters)])


def candidates() -> dict[str, Pipeline]:
    """Algorithmes comparés. Tous sont linéaires : sur quelques centaines de
    textes courts représentés par des milliers de variables creuses, ce sont
    les plus robustes ; les arbres (forêts, boosting) y sont peu adaptés."""
    return {
        "naive_bayes_mots": Pipeline([
            ("tfidf", _features(chars=False)), ("clf", ComplementNB(alpha=0.3))]),
        "reglog_mots": Pipeline([
            ("tfidf", _features(chars=False)),
            ("clf", LogisticRegression(C=10, max_iter=2000, random_state=SEED))]),
        "reglog_mots_caracteres": Pipeline([
            ("tfidf", _features()),
            ("clf", LogisticRegression(C=10, max_iter=2000, random_state=SEED))]),
        "svm_mots_caracteres_calibre": Pipeline([
            ("tfidf", _features()),
            ("clf", CalibratedClassifierCV(LinearSVC(C=0.5, random_state=SEED),
                                           method="sigmoid", cv=5))]),
    }


SELECTED = "reglog_mots_caracteres"


@dataclass
class Prediction:
    families: list[str]                 # familles retenues (1 ou 2)
    probabilities: dict[str, float]     # toutes les familles, triées


def predict(model: Pipeline, text: str) -> Prediction:
    probabilities = model.predict_proba([text])[0]
    ranked = sorted(zip(model.classes_, probabilities), key=lambda item: -item[1])
    families = [ranked[0][0]]
    if ranked[0][1] < SECOND_FAMILY_THRESHOLD:
        families.append(ranked[1][0])
    return Prediction(families, {name: round(float(p), 3) for name, p in ranked})


def explain(model: Pipeline, text: str, family: str, top: int = 5) -> list[tuple[str, float]]:
    """Mots ou fragments qui ont le plus poussé vers ``family`` (régression
    logistique uniquement) : contribution = valeur TF-IDF × coefficient."""
    features = model.named_steps["tfidf"]
    classifier = model.named_steps["clf"]
    if not hasattr(classifier, "coef_"):
        return []
    vector = features.transform([text]).toarray()[0]
    row = list(classifier.classes_).index(family)
    contributions = vector * classifier.coef_[row]
    names = features.get_feature_names_out()
    order = np.argsort(contributions)[::-1][:top]
    return [(names[i].split("__")[-1], round(float(contributions[i]), 3))
            for i in order if contributions[i] > 0]


def train(name: str = SELECTED) -> Pipeline:
    texts, labels = load(TRAIN_PATH)
    model = candidates()[name]
    model.fit(texts, labels)
    return model


def save(model: Pipeline, path: Path = MODEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load_model(path: Path = MODEL_PATH) -> Pipeline:
    return joblib.load(path)


if __name__ == "__main__":
    model = train()
    save(model)
    print(f"Modèle {SELECTED} enregistré : {MODEL_PATH}")
