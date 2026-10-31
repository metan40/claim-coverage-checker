"""Tests de la recherche des clauses."""
import sqlite3

import pytest

from src.database import DB_PATH
from src.retrieval import QUOTAS, fts_query, query_terms, retrieve, stem

VELO = "Mon vélo a disparu du local commun de la résidence, qui n'était pas fermé à clé."
BOUGIE = "Une bougie restée allumée sur la terrasse a fait fondre notre table de jardin."


def test_stem_keeps_short_words():
    assert stem("bicyclettes") == "bicyclett"
    assert stem("vol") == "vol"


def test_query_terms_drop_stop_words_and_add_synonyms():
    terms = query_terms(VELO)
    assert "mon" not in terms and "velo" in terms
    assert "bicyclette" in terms and "parties communes" in terms
    assert "bicyclette" not in query_terms(VELO, use_synonyms=False)


def test_fts_query_uses_prefixes_and_phrases():
    query = fts_query(["velos", "parties communes"])
    assert "velo*" in query and '"parties communes"' in query


needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="base non construite")


@pytest.fixture(scope="module")
def db():
    connection = sqlite3.connect(DB_PATH)
    yield connection
    connection.close()


@needs_db
def test_context_respects_quotas_and_contains_exclusions(db):
    clauses = retrieve(db, "sogessur_fr", VELO, ["vol"])
    assert len(clauses) <= sum(QUOTAS.values())
    assert any(c.type == "exclusion" for c in clauses)
    assert all(c.reason for c in clauses)


@needs_db
@pytest.mark.parametrize("contract, description, families, fragment", [
    ("sogessur_fr", VELO, ["vol"], "locaux à usage commun des occupants"),
    ("ethias_be", VELO, ["vol"], "uniquement si mention en est faite"),
    ("baloise_lu", BOUGIE, ["incendie"], "Détériorations ou brûlures causés au linge"),
    ("sogessur_fr", BOUGIE, ["incendie"], "fers à repasser et appareils de chauffage"),
])
def test_decisive_clause_in_context(db, contract, description, families, fragment):
    clauses = retrieve(db, contract, description, families)
    assert any(fragment in c.text for c in clauses)


@needs_db
def test_only_requested_contract(db):
    ids = {c.id for c in retrieve(db, "ethias_be", VELO, ["vol"])}
    contract_ids = {row[0] for row in db.execute(
        "SELECT a.id FROM articles a JOIN contrats c ON c.id = a.contrat_id WHERE c.code = 'ethias_be'")}
    assert ids <= contract_ids
