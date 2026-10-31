"""Comparaison des algorithmes de classification des sinistres.

- Validation croisée stratifiée (5 plis) sur le jeu d'entraînement généré.
- Test sur le jeu écrit à la main (tournures jamais vues) : c'est la mesure
  qui compte, la validation croisée sur des gabarits étant optimiste.
- Mesures : exactitude, F1 macro, exactitude top-2 (la bonne famille parmi
  les deux plus probables), log-loss et score de Brier (qualité des
  probabilités, utilisées pour décider de garder une deuxième famille).

Usage : ``python evaluation/evaluate_classifier.py`` (écrit
``evaluation/resultats_classifieur.md``).
"""
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss
from sklearn.model_selection import StratifiedKFold, cross_val_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.classifier import (FAMILIES, SECOND_FAMILY_THRESHOLD, SEED, SELECTED,  # noqa: E402
                            TEST_PATH, TRAIN_PATH, candidates, explain, load, predict)

OUT = Path(__file__).with_name("resultats_classifieur.md")
SHORT = {"vol": "vol", "incendie": "inc", "degats_des_eaux": "eau", "bris_de_glace": "bdg",
         "evenements_naturels": "nat", "responsabilite_civile": "rc"}


def brier(probabilities: np.ndarray, labels: list[str], classes) -> float:
    truth = np.array([[label == c for c in classes] for label in labels], dtype=float)
    return float(np.mean(np.sum((probabilities - truth) ** 2, axis=1)))


def main() -> None:
    train_texts, train_labels = load(TRAIN_PATH)
    test_texts, test_labels = load(TEST_PATH)
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    lines = ["# Comparaison des classifieurs de sinistres", "",
             f"Entraînement : {len(train_texts)} descriptions générées. "
             f"Test : {len(test_texts)} descriptions écrites à la main.", "",
             "| Modèle | F1 macro (validation croisée) | Exactitude test | F1 macro test "
             "| Top-2 test | Log-loss test | Brier test |",
             "|---|---|---|---|---|---|---|"]
    fitted = {}
    for name, model in candidates().items():
        cv = cross_val_score(model, train_texts, train_labels, cv=folds, scoring="f1_macro")
        model.fit(train_texts, train_labels)
        fitted[name] = model
        predicted = model.predict(test_texts)
        probabilities = model.predict_proba(test_texts)
        top2 = np.mean([label in model.classes_[np.argsort(p)[::-1][:2]]
                        for p, label in zip(probabilities, test_labels)])
        lines.append(
            f"| {name} | {cv.mean():.3f} ± {cv.std():.3f} | "
            f"{accuracy_score(test_labels, predicted):.3f} | "
            f"{f1_score(test_labels, predicted, average='macro'):.3f} | {top2:.3f} | "
            f"{log_loss(test_labels, probabilities, labels=model.classes_):.3f} | "
            f"{brier(probabilities, test_labels, model.classes_):.3f} |")

    model = fitted[SELECTED]
    predicted = model.predict(test_texts)
    lines += ["", f"## Modèle retenu : `{SELECTED}`", "",
              "Matrice de confusion sur le test (lignes : vraie famille ; colonnes : prédite) :", "",
              "| | " + " | ".join(SHORT[f] for f in FAMILIES) + " |",
              "|---" * (len(FAMILIES) + 1) + "|"]
    matrix = confusion_matrix(test_labels, predicted, labels=FAMILIES)
    for family, row in zip(FAMILIES, matrix):
        lines.append(f"| {SHORT[family]} | " + " | ".join(str(v) for v in row) + " |")

    kept = [predict(model, text) for text in test_texts]
    covered = np.mean([label in p.families for p, label in zip(kept, test_labels)])
    two = np.mean([len(p.families) == 2 for p in kept])
    lines += ["", f"Règle « deuxième famille si probabilité < {SECOND_FAMILY_THRESHOLD} » : "
              f"la bonne famille est retenue dans {covered:.0%} des cas, "
              f"avec deux familles retenues dans {two:.0%} des cas.", "",
              "## Erreurs du modèle retenu", "",
              "| Id | Description | Vraie | Prédite (probabilité) | Mots décisifs |",
              "|---|---|---|---|---|"]
    ids = [f"T{i:03d}" for i in range(1, len(test_texts) + 1)]
    for identifier, text, label, prediction in zip(ids, test_texts, test_labels, kept):
        best = next(iter(prediction.probabilities))
        if best != label:
            words = ", ".join(w for w, _ in explain(model, text, best, top=4))
            lines.append(f"| {identifier} | {text} | {label} | {best} "
                         f"({prediction.probabilities[best]:.2f}) | {words} |")

    lines += ["", "## Cas du sujet", ""]
    for identifier, text in zip(ids, test_texts):
        if identifier in ("T001", "T002"):
            p = predict(model, text)
            top = ", ".join(f"{k} {v:.2f}" for k, v in list(p.probabilities.items())[:3])
            lines.append(f"- {identifier} « {text} » → retenues : {', '.join(p.families)} ({top})")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
