"""Banc d'essai des classifieurs de sinistres : du TF-IDF aux transformeurs.

Tous les modèles apprennent sur le même jeu généré
(``data/sinistres/sinistres_entrainement.csv``) et sont jugés sur le même jeu
écrit à la main (``data/sinistres/sinistres_test.csv``), jamais vu.

Modèles comparés
----------------
- ``tfidf_reglog``      : TF-IDF mots + caractères, régression logistique (référence)
- ``tfidf_svm``         : idem, SVM linéaire calibré
- ``e5_reglog``         : plongements multilingual-e5-small, régression logistique
- ``e5_boosting``       : plongements multilingual-e5-small, gradient boosting (scikit-learn)
- ``setfit_e5``         : SetFit (ajustement contrastif de e5-small, puis tête logistique)
- ``camembert``         : DistilCamemBERT ajusté de bout en bout (option ``--camembert``)
- ``llm_zero_shot``     : llama3.2 via Ollama, sans apprentissage (option ``--llm``)

Mesures
-------
Exactitude et F1 macro avec intervalle de confiance à 95 % (bootstrap,
2 000 tirages), top-2, log-loss et score de Brier (qualité des probabilités),
différence d'exactitude avec la référence (bootstrap apparié : la différence
est-elle significative ?), temps d'entraînement, temps de prédiction par
description, taille du modèle.

Usage (voir ``docs/guide_benchmark_pc.md``) :
    python evaluation/benchmark_modeles.py              # modèles de base
    python evaluation/benchmark_modeles.py --camembert  # + DistilCamemBERT (plus long)
    python evaluation/benchmark_modeles.py --llm        # + llama3.2 (Ollama lancé)

Résultats : ``evaluation/resultats_benchmark.md`` et ``.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, log_loss

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.classifier import FAMILIES, TEST_PATH, TRAIN_PATH, candidates, load  # noqa: E402

SEED = 2026
BOOTSTRAP = 2000
E5 = "intfloat/multilingual-e5-small"
CAMEMBERT = "cmarkea/distilcamembert-base"
OUT_MD = Path(__file__).with_name("resultats_benchmark.md")
OUT_JSON = Path(__file__).with_name("resultats_benchmark.json")


# --- Outils de mesure ----------------------------------------------------------

def probabilities_in_order(classes, probabilities) -> np.ndarray:
    """Réordonne les colonnes de probabilités selon FAMILIES."""
    index = [list(classes).index(f) for f in FAMILIES]
    return np.asarray(probabilities)[:, index]


def bootstrap_ci(y_true, y_pred, metric, rng) -> tuple[float, float]:
    n = len(y_true)
    values = []
    for _ in range(BOOTSTRAP):
        sample = rng.integers(0, n, n)
        values.append(metric([y_true[i] for i in sample], [y_pred[i] for i in sample]))
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def paired_difference(y_true, pred_a, pred_b, rng) -> tuple[float, float, float]:
    """Différence d'exactitude b - a et son intervalle (bootstrap apparié)."""
    correct_a = np.array([t == p for t, p in zip(y_true, pred_a)], dtype=float)
    correct_b = np.array([t == p for t, p in zip(y_true, pred_b)], dtype=float)
    n = len(y_true)
    diffs = []
    for _ in range(BOOTSTRAP):
        sample = rng.integers(0, n, n)
        diffs.append(correct_b[sample].mean() - correct_a[sample].mean())
    return (float(correct_b.mean() - correct_a.mean()), float(np.percentile(diffs, 2.5)),
            float(np.percentile(diffs, 97.5)))


def directory_size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


def evaluate(name, y_test, probabilities, train_seconds, predict_seconds, size_mb, rng):
    probabilities = np.clip(np.asarray(probabilities, dtype=float), 1e-9, 1)
    probabilities = probabilities / probabilities.sum(axis=1, keepdims=True)
    predicted = [FAMILIES[i] for i in probabilities.argmax(axis=1)]
    truth = np.array([[label == f for f in FAMILIES] for label in y_test], dtype=float)
    top2 = np.mean([label in [FAMILIES[i] for i in np.argsort(p)[::-1][:2]]
                    for p, label in zip(probabilities, y_test)])
    macro = lambda a, b: f1_score(a, b, average="macro", labels=FAMILIES, zero_division=0)  # noqa: E731
    return {
        "modele": name,
        "exactitude": accuracy_score(y_test, predicted),
        "exactitude_ic95": bootstrap_ci(y_test, predicted, accuracy_score, rng),
        "f1_macro": macro(y_test, predicted),
        "f1_macro_ic95": bootstrap_ci(y_test, predicted, macro, rng),
        "top2": float(top2),
        # log_loss attend les colonnes dans l'ordre alphabétique des étiquettes
        "log_loss": float(log_loss(y_test, probabilities[:, [FAMILIES.index(f) for f in sorted(FAMILIES)]],
                                   labels=sorted(FAMILIES))),
        "brier": float(np.mean(np.sum((probabilities - truth) ** 2, axis=1))),
        "entrainement_s": round(train_seconds, 1),
        "prediction_ms_par_texte": round(1000 * predict_seconds / len(y_test), 1),
        "taille_mo": round(size_mb, 1),
        "predictions": predicted,
    }


# --- Modèles -------------------------------------------------------------------

def run_sklearn(name, x_train, y_train, x_test):
    import joblib
    model = candidates()[{"tfidf_reglog": "reglog_mots_caracteres",
                          "tfidf_svm": "svm_mots_caracteres_calibre"}[name]]
    start = time.perf_counter()
    model.fit(x_train, y_train)
    train = time.perf_counter() - start
    start = time.perf_counter()
    probabilities = model.predict_proba(x_test)
    predict = time.perf_counter() - start
    with tempfile.TemporaryDirectory() as folder:
        joblib.dump(model, Path(folder) / "m.joblib")
        size = directory_size_mb(Path(folder))
    return probabilities_in_order(model.classes_, probabilities), train, predict, size


_encoder = {}


def e5_encode(texts):
    """Plongements e5 : le préfixe « query: » est celui que demande le modèle."""
    from sentence_transformers import SentenceTransformer
    if "model" not in _encoder:
        _encoder["model"] = SentenceTransformer(E5, device="cpu")
    return _encoder["model"].encode([f"query: {t}" for t in texts], batch_size=32,
                                    normalize_embeddings=True, show_progress_bar=False)


def run_embeddings(name, x_train, y_train, x_test):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    start = time.perf_counter()
    train_vectors = e5_encode(x_train)
    if name == "e5_reglog":
        head = LogisticRegression(C=10, max_iter=3000, random_state=SEED)
    else:
        head = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.1, random_state=SEED)
    head.fit(train_vectors, y_train)
    train = time.perf_counter() - start
    start = time.perf_counter()
    probabilities = head.predict_proba(e5_encode(x_test))
    predict = time.perf_counter() - start
    from huggingface_hub import snapshot_download
    size = directory_size_mb(Path(snapshot_download(E5)))
    return probabilities_in_order(head.classes_, probabilities), train, predict, size


def run_setfit(x_train, y_train, x_test):
    from datasets import Dataset
    from setfit import SetFitModel, Trainer, TrainingArguments
    model = SetFitModel.from_pretrained(E5, labels=FAMILIES)
    label_ids = [FAMILIES.index(y) for y in y_train]
    train_set = Dataset.from_dict({"text": [f"query: {t}" for t in x_train], "label": label_ids})
    args = TrainingArguments(batch_size=32, num_epochs=1, num_iterations=5, seed=SEED)
    trainer = Trainer(model=model, args=args, train_dataset=train_set)
    start = time.perf_counter()
    trainer.train()
    train = time.perf_counter() - start
    start = time.perf_counter()
    probabilities = model.predict_proba([f"query: {t}" for t in x_test]).numpy()
    predict = time.perf_counter() - start
    with tempfile.TemporaryDirectory() as folder:
        model.save_pretrained(folder)
        size = directory_size_mb(Path(folder))
    return probabilities, train, predict, size     # colonnes déjà dans l'ordre de FAMILIES


def run_camembert(x_train, y_train, x_test):
    import torch
    from datasets import Dataset
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, Trainer,
                              TrainingArguments)
    torch.manual_seed(SEED)
    tokenizer = AutoTokenizer.from_pretrained(CAMEMBERT)
    model = AutoModelForSequenceClassification.from_pretrained(CAMEMBERT, num_labels=len(FAMILIES))
    data = Dataset.from_dict({"text": x_train, "label": [FAMILIES.index(y) for y in y_train]})
    data = data.map(lambda b: tokenizer(b["text"], truncation=True, max_length=96,
                                        padding="max_length"), batched=True)
    with tempfile.TemporaryDirectory() as folder:
        args = TrainingArguments(output_dir=folder, num_train_epochs=3,
                                 per_device_train_batch_size=16, learning_rate=5e-5,
                                 seed=SEED, report_to=[], save_strategy="no", logging_steps=50)
        start = time.perf_counter()
        Trainer(model=model, args=args, train_dataset=data).train()
        train = time.perf_counter() - start
        model.eval()
        start = time.perf_counter()
        with torch.no_grad():
            encoded = tokenizer(x_test, truncation=True, max_length=96, padding=True,
                                return_tensors="pt")
            probabilities = torch.softmax(model(**encoded).logits, dim=-1).numpy()
        predict = time.perf_counter() - start
        model.save_pretrained(folder + "/m")
        size = directory_size_mb(Path(folder + "/m"))
    return probabilities, train, predict, size


def run_llm(x_test):
    """LLM sans apprentissage : on lui donne la liste des familles et un exemple
    de chaque. Une réponse hors liste compte comme une erreur (probabilité
    uniforme)."""
    import urllib.request
    url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
    model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    schema = {"type": "object", "properties": {"famille": {"type": "string", "enum": FAMILIES}},
              "required": ["famille"]}
    instructions = (
        "Classe le sinistre d'assurance habitation dans une seule famille de garantie : "
        "vol (vol, cambriolage, vandalisme), incendie (feu, fumée, explosion, foudre, brûlure), "
        "degats_des_eaux (fuite, infiltration, débordement), bris_de_glace (vitre, miroir, "
        "vitrocéramique), evenements_naturels (tempête, grêle, neige, inondation, sécheresse), "
        "responsabilite_civile (dommage causé à autrui). Réponds en JSON.\n\nSinistre : ")
    probabilities, start = [], time.perf_counter()
    for text in x_test:
        payload = json.dumps({"model": model, "prompt": instructions + text, "stream": False,
                              "format": schema, "options": {"temperature": 0, "num_predict": 30}})
        request = urllib.request.Request(url, data=payload.encode(),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                family = json.loads(json.loads(response.read())["response"])["famille"]
            row = [0.97 if f == family else 0.03 / (len(FAMILIES) - 1) for f in FAMILIES]
        except Exception:
            row = [1 / len(FAMILIES)] * len(FAMILIES)
        probabilities.append(row)
    return np.array(probabilities), 0.0, time.perf_counter() - start, 0.0


# --- Rapport -------------------------------------------------------------------

def report(results, errors, y_test, rng, args):
    reference = next((r for r in results if r["modele"] == "tfidf_reglog"), None)
    lines = ["# Banc d'essai des classifieurs de sinistres", "",
             f"Entraînement : 780 descriptions générées · test : {len(y_test)} descriptions "
             "écrites à la main, jamais vues. Intervalles de confiance à 95 % par bootstrap "
             f"({BOOTSTRAP} tirages).", "",
             f"Machine : {platform.processor() or platform.machine()} · "
             f"{os.cpu_count()} cœurs · Python {platform.python_version()} · sans GPU", "",
             "| Modèle | Exactitude [IC 95 %] | F1 macro [IC 95 %] | Top-2 | Log-loss | Brier "
             "| Écart avec la référence [IC 95 %] | Entraînement | Prédiction / texte | Taille |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: -r["f1_macro"]):
        gap = "—"
        if reference and r is not reference:
            d, low, high = paired_difference(y_test, reference["predictions"], r["predictions"], rng)
            mark = " (significatif)" if low > 0 or high < 0 else ""
            gap = f"{d:+.1%} [{low:+.1%} ; {high:+.1%}]{mark}"
        lines.append(
            f"| {r['modele']} | {r['exactitude']:.1%} [{r['exactitude_ic95'][0]:.0%} ; "
            f"{r['exactitude_ic95'][1]:.0%}] | {r['f1_macro']:.3f} [{r['f1_macro_ic95'][0]:.2f} ; "
            f"{r['f1_macro_ic95'][1]:.2f}] | {r['top2']:.1%} | {r['log_loss']:.3f} | "
            f"{r['brier']:.3f} | {gap} | {r['entrainement_s']} s | "
            f"{r['prediction_ms_par_texte']} ms | {r['taille_mo']} Mo |")
    if errors:
        lines += ["", "## Modèles non évalués", ""] + [f"- {k} : {v}" for k, v in errors.items()]
    lines += ["", "## Erreurs par modèle (identifiant du cas : vraie → prédite)", ""]
    ids = [f"T{i:03d}" for i in range(1, len(y_test) + 1)]
    for r in results:
        wrong = [f"{i} : {t} → {p}" for i, t, p in zip(ids, y_test, r["predictions"]) if t != p]
        lines.append(f"- **{r['modele']}** ({len(wrong)}) : " + ("; ".join(wrong) or "aucune"))
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps({"options": vars(args), "resultats": results,
                                    "erreurs": errors}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--camembert", action="store_true", help="ajouter DistilCamemBERT (lent)")
    parser.add_argument("--llm", action="store_true", help="ajouter llama3.2 via Ollama")
    parser.add_argument("--seulement", nargs="*", help="noms de modèles à lancer")
    args = parser.parse_args()
    x_train, y_train = load(TRAIN_PATH)
    x_test, y_test = load(TEST_PATH)
    rng = np.random.default_rng(SEED)

    plan = {
        "tfidf_reglog": lambda: run_sklearn("tfidf_reglog", x_train, y_train, x_test),
        "tfidf_svm": lambda: run_sklearn("tfidf_svm", x_train, y_train, x_test),
        "e5_reglog": lambda: run_embeddings("e5_reglog", x_train, y_train, x_test),
        "e5_boosting": lambda: run_embeddings("e5_boosting", x_train, y_train, x_test),
        "setfit_e5": lambda: run_setfit(x_train, y_train, x_test),
    }
    if args.camembert:
        plan["camembert"] = lambda: run_camembert(x_train, y_train, x_test)
    if args.llm:
        plan["llm_zero_shot"] = lambda: run_llm(x_test)
    if args.seulement:
        plan = {k: v for k, v in plan.items() if k in args.seulement or k == "tfidf_reglog"}

    results, errors = [], {}
    for name, run in plan.items():
        print(f"→ {name}…", flush=True)
        try:
            probabilities, train, predict, size = run()
            results.append(evaluate(name, y_test, probabilities, train, predict, size, rng))
            print(f"  exactitude {results[-1]['exactitude']:.1%}, "
                  f"F1 macro {results[-1]['f1_macro']:.3f}", flush=True)
        except Exception as error:   # un modèle en échec n'arrête pas le banc d'essai
            errors[name] = f"{type(error).__name__}: {error}"
            traceback.print_exc()
    report(results, errors, y_test, rng, args)


if __name__ == "__main__":
    main()
