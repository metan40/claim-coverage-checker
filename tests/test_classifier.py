"""Tests du classifieur de sinistres (modèle entraîné à la volée, en mémoire)."""
import pytest

from src.classifier import FAMILIES, SECOND_FAMILY_THRESHOLD, explain, predict, train


@pytest.fixture(scope="module")
def model():
    return train()


def test_all_families_known(model):
    assert sorted(model.classes_) == sorted(FAMILIES)


def test_subject_cases(model):
    assert "vol" in predict(model, "Mon vélo a disparu du local commun, le local n'était pas fermé à clé.").families
    candle = predict(model, "Une bougie laissée sur la table du jardin a fondu avec la chaleur et abîmé la table.")
    assert candle.families[0] == "incendie"


def test_second_family_when_unsure(model):
    prediction = predict(model, "Il s'est passé quelque chose à la maison.")
    top = next(iter(prediction.probabilities.values()))
    assert (len(prediction.families) == 2) == (top < SECOND_FAMILY_THRESHOLD)


def test_probabilities_sum_to_one(model):
    total = sum(predict(model, "La vitre du salon est cassée.").probabilities.values())
    assert total == pytest.approx(1.0, abs=0.01)


def test_explanation_points_to_relevant_words(model):
    words = " ".join(w for w, _ in explain(model, "Des cambrioleurs ont forcé la porte.", "vol"))
    assert "cambriol" in words
