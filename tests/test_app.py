# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : tests/test_app.py
# Auteur  : Thierry MBARGA
# Rôle    : API : routes appelées directement, sans serveur ni modèle de
#           langage
# Lancer  : python -m pytest tests/test_app.py
# ---------------------------------------------------------------------------
"""API : routes appelées directement, sans serveur ni modèle de langage."""
import json

import pytest


@pytest.fixture(scope="module")
def api(monkeypatch_module):
    monkeypatch_module.setenv("USE_LLM", "0")
    import importlib
    import src.app as app
    return importlib.reload(app)


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_model_name_typo_is_tolerated(api):
    assert api.normalize_model_name(" llama3.2:3b. ") == "llama3.2:3b"


def test_ready_without_llm(api):
    response = api.ready()
    body = response.body if hasattr(response, "body") else response.content
    body = json.loads(body) if isinstance(body, (bytes, str)) else body
    assert response.status_code == 200 and body["status"] == "ready"


def test_demo_claim_is_instructed_with_seven_controls(api):
    result = api.instruire_sinistre(api.NouveauSinistre(sinistre_id="S-01"))
    numeros = {c["numero"] for c in result["controles"]}
    assert numeros == set(range(1, 8))
    # sans modèle, les contrôles d'interprétation restent à vérifier : jamais « couvert »
    assert result["verdict"] in ("indetermine", "potentiellement_exclu")
    assert result["avertissement"]


def test_new_claim_is_recorded_in_memory_only(api):
    import sqlite3
    from src.database import DB_PATH
    before = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM sinistres").fetchone()[0]
    result = api.instruire_sinistre(api.NouveauSinistre(
        police="BE-DEMO-02", description="Une poêle a pris feu dans la cuisine.",
        date_survenance="2026-09-11", montant_estime=1500))
    assert result["sinistre"]["id"].startswith("WEB-")
    assert sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM sinistres").fetchone()[0] == before


def test_unknown_policy_is_refused(api):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        api.instruire_sinistre(api.NouveauSinistre(
            police="XX-0", description="feu", date_survenance="2026-09-11"))


def test_expired_policy_blocks(api):
    result = api.instruire_sinistre(api.NouveauSinistre(sinistre_id="S-06"))
    assert result["verdict"] == "potentiellement_exclu"
    assert result["nature"] == "contrat non en vigueur"
