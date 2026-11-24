# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : tests/test_instruction.py
# Auteur  : Thierry MBARGA
# Rôle    : Tests de l'instruction factuelle d'un sinistre (contrôles 1, 2,
#           3, 6, 7) et de la règle de verdict non compensatoire
# Lancer  : python -m pytest tests/test_instruction.py
# ---------------------------------------------------------------------------
"""Tests de l'instruction factuelle d'un sinistre (contrôles 1, 2, 3, 6, 7)
et de la règle de verdict non compensatoire."""
import sqlite3
from datetime import date

import pytest

from src.database import DB_PATH
from src.instruction import (Controle, controle_contrat, indemnite, instruire, jours_ouvres,
                             verdict)

needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="base non construite")


# --- Fonctions de calcul ------------------------------------------------------

def test_jours_ouvres_skip_weekends():
    vendredi, lundi, mercredi = date(2026, 9, 11), date(2026, 9, 14), date(2026, 9, 16)
    assert jours_ouvres(vendredi, lundi) == 1
    assert jours_ouvres(vendredi, mercredi) == 3
    assert jours_ouvres(lundi, lundi) == 0


@pytest.mark.parametrize("dommage, franchise, plafond, attendu", [
    (900, 150, 30_000, 750),      # cas courant
    (100, 150, 30_000, 0),        # sous la franchise
    (9_000, 150, 5_000, 5_000),   # plafond atteint
])
def test_indemnite(dommage, franchise, plafond, attendu):
    assert indemnite(dommage, franchise, plafond) == attendu


# --- Règle de verdict ----------------------------------------------------------

def _c(numero, statut):
    return Controle(numero, "test", statut, "", "")


def test_one_blocking_control_is_enough():
    controles = [_c(1, "satisfait"), _c(3, "bloquant"), _c(5, "satisfait"), _c(7, "satisfait")]
    assert verdict(controles) == ("potentiellement_exclu", "garantie non souscrite")


def test_all_satisfied_means_covered():
    assert verdict([_c(1, "satisfait"), _c(4, "sans_objet"), _c(7, "satisfait")]) == \
        ("potentiellement_couvert", None)


def test_missing_information_means_undetermined():
    assert verdict([_c(1, "satisfait"), _c(5, "a_verifier")]) == ("indetermine", None)


def test_good_results_never_compensate_a_block():
    controles = [_c(n, "satisfait") for n in range(1, 8)] + [_c(5, "bloquant")]
    assert verdict(controles)[0] == "potentiellement_exclu"


# --- Contrôle 1 -----------------------------------------------------------------

def test_contract_in_force():
    police = {"numero": "P", "date_effet": "2025-01-01", "date_fin": None}
    assert controle_contrat(police, date(2026, 1, 1)).statut == "satisfait"
    assert controle_contrat(police, date(2024, 12, 31)).statut == "bloquant"
    ended = dict(police, date_fin="2026-06-01")
    assert controle_contrat(ended, date(2026, 6, 1)).statut == "bloquant"
    assert controle_contrat(None, date(2026, 1, 1)).statut == "bloquant"


# --- Sinistres de démonstration --------------------------------------------------

@pytest.fixture(scope="module")
def db():
    connection = sqlite3.connect(DB_PATH)
    yield connection
    connection.close()


def _statut(instruction, numero, nom=None):
    return next(c.statut for c in instruction.controles
                if c.numero == numero and (nom is None or c.nom == nom))


@needs_db
@pytest.mark.parametrize("sinistre, familles, numero, statut", [
    ("S-01", ["vol"], 3, "satisfait"),        # formule Confort : vol inclus
    ("S-04", ["vol"], 3, "bloquant"),         # Baloise sans option vol
    ("S-05", ["vol"], 3, "bloquant"),         # Sogessur Initiale sans option vol
    ("S-06", ["vol"], 1, "bloquant"),         # contrat résilié
    ("S-08", ["incendie"], 3, "satisfait"),   # pack jardin souscrit
    ("S-11", ["incendie"], 3, "bloquant"),    # mobilier de jardin sans pack
])
def test_demo_claims(db, sinistre, familles, numero, statut):
    assert _statut(instruire(db, sinistre, familles), numero) == statut


@needs_db
def test_late_declaration_is_never_blocking(db):
    instruction = instruire(db, "S-07", ["vol"])      # 3 jours ouvrés pour un vol en France
    assert _statut(instruction, 6, "Délai de déclaration") == "a_verifier"
    assert instruction.verdict == "indetermine"


@needs_db
def test_guarantee_cap_applies(db):
    instruction = instruire(db, "S-08", ["incendie"])    # pack jardin Sogessur plafonné à 5 000 €
    assert instruction.indemnite == 200


@needs_db
def test_every_guarantee_is_linked_to_its_clause(db):
    missing = db.execute("SELECT count(*) FROM garanties WHERE article_id IS NULL").fetchone()[0]
    assert missing == 0
