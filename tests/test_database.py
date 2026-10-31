"""Tests de la base des conditions générales.

Les tests unitaires portent sur les règles de typage et de familles. Les
tests d'intégration vérifient, dans la base livrée, la présence et le
type des clauses décisives des deux sinistres du sujet.
"""
import sqlite3

import pytest

from src.database import DB_PATH, article_families, article_type, normalize


def test_normalize_removes_accents_and_apostrophes():
    assert normalize("Qu’est-ce  qui n’est PAS assuré ?") == "qu'est-ce qui n'est pas assure ?"


@pytest.mark.parametrize("section, text, expected", [
    ("1. Définitions > Incendie", "Combustion avec flamme en dehors d'un foyer normal.", "definition"),
    ("Chapitre VII Lexique > Meubles de jardin", "Le mobilier de jardin...", "definition"),
    ("Les événements garantis > CE QUI EST EXCLU", "Les vols des biens déposés...", "exclusion"),
    ("4.4. Qu’est-ce qui n’est pas assuré ?", "Nous n'intervenons pas pour le vol", "exclusion"),
    ("Vol", "Ne sont pas garantis les vols commis sans effraction.", "exclusion"),
    ("Mesures de sécurité que vous devez respecter", "En cas d'absence, fermez à clé.", "condition"),
    ("Vol", "La garantie est acquise à condition que les portes soient verrouillées.", "condition"),
    ("Vol", "Nous garantissons le vol commis par effraction.", "garantie"),
])
def test_article_type(section, text, expected):
    assert article_type(section, text) == expected


def test_conditions_generales_title_does_not_make_everything_a_condition():
    section = "CONDITIONS GÉNÉRALES > Les événements garantis > Ce qui est garanti"
    assert article_type(section, "Le vol commis par effraction.") == "garantie"


def test_families_are_multi_label():
    families = article_families("Les Packs", "Le vol de bicyclettes non attachées. Le vol des vélos.")
    assert {"vol", "mobilite"} <= set(families)


def test_family_requires_heading_or_two_mentions():
    assert "incendie" not in article_families("Vol", "Une seule mention de fumée.")
    assert "incendie" in article_families("Incendie et événements assimilés", "Texte.")


# --- Base livrée ---------------------------------------------------------------

needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="base non construite")


@pytest.fixture(scope="module")
def db():
    connection = sqlite3.connect(DB_PATH)
    yield connection
    connection.close()


def _find(db, code, fragment):
    return db.execute(
        "SELECT a.page, a.type FROM articles a JOIN contrats c ON c.id = a.contrat_id"
        " WHERE c.code = ? AND a.texte LIKE ?", (code, f"%{fragment}%")).fetchall()


@needs_db
def test_three_contracts_loaded(db):
    codes = {row[0] for row in db.execute("SELECT code FROM contrats")}
    assert codes == {"baloise_lu", "ethias_be", "sogessur_fr"}


@needs_db
@pytest.mark.parametrize("code, fragment, expected_type", [
    # Vélo volé dans le local commun
    ("sogessur_fr", "locaux à usage commun des occupants", "exclusion"),
    ("sogessur_fr", "non attachés à un point fixe", "exclusion"),
    ("ethias_be", "parties communes", "exclusion"),
    ("baloise_lu", "point d’attache fixé au sol", "condition"),
    ("baloise_lu", "portes d’accès doivent être fermées à clé", "condition"),
    # Bougie et table de jardin
    ("sogessur_fr", "fers à repasser et appareils de chauffage", "exclusion"),
    ("baloise_lu", "Détériorations ou brûlures causés au linge", "definition"),
])
def test_decisive_clauses_are_present_and_typed(db, code, fragment, expected_type):
    rows = _find(db, code, fragment)
    assert rows, f"clause introuvable : {fragment}"
    assert expected_type in {kind for _, kind in rows}


@needs_db
def test_full_text_search_ignores_accents(db):
    rows = db.execute("SELECT count(*) FROM articles_fts WHERE articles_fts MATCH 'menagers'").fetchone()
    assert rows[0] > 0
