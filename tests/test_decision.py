"""Tests de l'analyse de couverture, avec un faux LLM (sans Ollama)."""
import json
import sqlite3

import pytest

from src.database import SCHEMA
from src.decision import analyse, build_prompt, extract_is_in_clause, record, verify
from src.retrieval import Clause

EXCLUSION = Clause(10, 17, "Vol > CE QUI EST EXCLU", "exclusion",
                   "Les vols des biens déposés dans les locaux à usage commun des occupants de l'immeuble.")
HEADER = Clause(11, 16, "Les événements garantis > Vol", "garantie",
                "Cette garantie vous est acquise si vous avez souscrit une formule Initiale avec option Vol.",
                reason="en-tête de la garantie vol")
GUARANTEE = Clause(12, 16, "Vol > Ce qui est garanti", "garantie",
                   "Le vol commis par effraction, escalade ou usage de fausses clés.")
CLAUSES = [HEADER, GUARANTEE, EXCLUSION]
DESCRIPTION = "Mon vélo a disparu du local commun de l'immeuble."


def fake(answer: dict):
    return lambda prompt: json.dumps(answer)


def answer(verdict, clauses, missing=None):
    return {"verdict": verdict, "justification": "…", "clauses": clauses,
            "conditions_a_verifier": [], "informations_manquantes": missing or []}


def test_prompt_numbers_clauses_and_contains_claim():
    prompt = build_prompt(DESCRIPTION, "Sogessur", CLAUSES)
    assert "C1 | garantie | p.16" in prompt and "C3 | exclusion | p.17" in prompt
    assert DESCRIPTION in prompt


def test_extract_verification():
    assert extract_is_in_clause("biens déposés dans les locaux à usage commun", EXCLUSION.text)
    assert extract_is_in_clause("Les vols des biens déposés dans les locaux communs à usage commun",
                                EXCLUSION.text)
    assert not extract_is_in_clause("les vélos sont toujours garantis partout", EXCLUSION.text)


def test_correct_exclusion_is_kept():
    decision = analyse(DESCRIPTION, "Sogessur", CLAUSES, ["vol"], llm=fake(answer(
        "potentiellement_exclu",
        [{"ref": "C3", "nature": "exclusion", "extrait": "biens déposés dans les locaux à usage commun",
          "effet": "exclut le vol"}])))
    assert decision.verdict == "potentiellement_exclu"
    assert decision.clauses[0].page == 17 and decision.clauses[0].extrait_verifie


def test_invented_clause_is_dropped_and_verdict_downgraded():
    decision = verify(answer("potentiellement_couvert",
                             [{"ref": "C9", "nature": "garantie", "extrait": "tout est couvert", "effet": ""}]),
                      CLAUSES, ["vol"])
    assert decision.verdict == "indetermine"
    assert not decision.clauses
    assert any("non fournie" in a for a in decision.ajustements)


def test_covered_with_cited_exclusion_becomes_indeterminate():
    decision = verify(answer("potentiellement_couvert", [
        {"ref": "C2", "nature": "garantie", "extrait": "Le vol commis par effraction, escalade", "effet": ""},
        {"ref": "C3", "nature": "exclusion", "extrait": "locaux à usage commun des occupants", "effet": ""}]),
        CLAUSES, ["vol"])
    assert decision.verdict == "indetermine"


def test_excluded_without_limiting_clause_becomes_indeterminate():
    decision = verify(answer("potentiellement_exclu", [
        {"ref": "C2", "nature": "garantie", "extrait": "Le vol commis par effraction, escalade", "effet": ""}]),
        CLAUSES, ["vol"])
    assert decision.verdict == "indetermine"


def test_optional_guarantee_and_checklist_questions_added():
    decision = verify(answer("indetermine", []), CLAUSES, ["vol"])
    questions = " ".join(decision.informations_manquantes)
    assert "souscrite" in questions and "p.16" in questions
    assert "plainte" in questions


def test_model_unavailable_gives_useful_indeterminate():
    def broken(prompt):
        raise TimeoutError
    decision = analyse(DESCRIPTION, "Sogessur", CLAUSES, ["vol"], llm=broken)
    assert decision.verdict == "indetermine" and decision.verdict_modele is None
    assert decision.informations_manquantes
    assert "aide à la décision" in decision.avertissement.lower()


def test_invalid_json_is_handled():
    decision = analyse(DESCRIPTION, "Sogessur", CLAUSES, ["vol"], llm=lambda p: "pas du json")
    assert decision.verdict == "indetermine"


def test_record_writes_decision():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    connection.execute("INSERT INTO contrats (code, gamme, assureur, pays, produit, date_effet, fichier,"
                       " sha256) VALUES ('x','x','A','LU','Home','2024-01-01','x.pdf','0')")
    decision = verify(answer("indetermine", []), CLAUSES, ["vol"])
    record(connection, 1, DESCRIPTION, {"vol": 0.9}, decision)
    assert connection.execute("SELECT verdict FROM decisions").fetchone()[0] == "indetermine"
