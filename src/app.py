# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : src/app.py
# Auteur  : Thierry MBARGA
# Rôle    : serveur web (FastAPI). Reçoit un sinistre, appelle le classifieur
#           puis les 7 contrôles, renvoie le résultat à la page web.
# Entrée  : requêtes HTTP de static/index.html.
# Sortie  : réponses JSON (verdict, contrôles, sources, indemnité).
# ---------------------------------------------------------------------------
"""API et interface web de l'instruction d'un sinistre.

Routes :

* ``GET /`` : interface web (``static/index.html``) ;
* ``GET /health`` : l'API répond ;
* ``GET /ready`` : base, classifieur, Ollama et modèle disponibles (503 sinon) ;
* ``GET /version`` : version et modèle configuré ;
* ``GET /api/polices`` et ``GET /api/sinistres`` : données de démonstration ;
* ``POST /api/instruire`` : instruit un sinistre de démonstration
  (``sinistre_id``) ou un nouveau sinistre (police, description, dates...).

La base livrée n'est jamais modifiée : l'application travaille sur une copie
en mémoire, où sont aussi enregistrés les sinistres saisis dans l'interface.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import urllib.request
import uuid
from dataclasses import asdict
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.classifier import load_model, predict
from src.database import DB_PATH
from src.decision import OLLAMA_MODEL, OLLAMA_URL, WARNING, call_ollama
from src.instruction import instruire

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
OLLAMA_TAGS = OLLAMA_URL.replace("/api/generate", "/api/tags")
USE_LLM = os.getenv("USE_LLM", "1") != "0"


# Corrige un nom de modèle saisi avec un point final par erreur.
def normalize_model_name(name: str) -> str:
    """« llama3.2:3b. » saisi par erreur reste valide."""
    return name.strip().rstrip(".").strip()


# Copie la base SQLite livrée en mémoire : l'application peut y écrire
# (sinistres saisis) sans jamais modifier le fichier d'origine.
def memory_copy(path: Path = DB_PATH) -> sqlite3.Connection:
    source = sqlite3.connect(path)
    # check_same_thread=False : FastAPI répond depuis plusieurs fils d'exécution ;
    # le verrou `lock` ci-dessous empêche deux accès simultanés.
    copy = sqlite3.connect(":memory:", check_same_thread=False)
    # backup() copie tables, index et index plein texte FTS5.
    source.backup(copy)
    source.close()
    copy.row_factory = sqlite3.Row
    return copy


# Chargés une seule fois au démarrage : base en mémoire, verrou,
# classifieur déjà entraîné (models/classifieur_sinistres.joblib).
connection = memory_copy()
lock = threading.Lock()
classifier = load_model()

app = FastAPI(title="claim-coverage-checker", version=VERSION)


# Corps de POST /api/instruire. Pydantic valide les types avant le code :
# dates réelles, montant >= 0, description de 2000 caractères au plus.
class NouveauSinistre(BaseModel):
    sinistre_id: str | None = Field(None, description="sinistre de démonstration à instruire")
    police: str | None = None
    description: str | None = Field(None, max_length=2000)
    date_survenance: date | None = None
    date_connaissance: date | None = None
    date_declaration: date | None = None
    bien: str | None = None
    montant_estime: float | None = Field(None, ge=0)


def ollama_status() -> tuple[bool, bool]:
    """(Ollama répond, modèle présent)."""
    try:
        # /api/tags d'Ollama liste les modèles téléchargés ; délai court (5 s)
        # pour que /ready réponde vite même si Ollama est arrêté.
        with urllib.request.urlopen(OLLAMA_TAGS, timeout=5) as response:
            models = [m.get("name", "") for m in json.loads(response.read()).get("models", [])]
    except Exception:
        return False, False
    wanted = normalize_model_name(OLLAMA_MODEL)
    # Présent si le nom correspond exactement, ou si le nom demandé n'a pas
    # d'étiquette (« llama3.2 » accepte « llama3.2:latest »).
    return True, any(m == wanted or m.split(":")[0] == wanted and ":" not in wanted for m in models)


# --- Routes -------------------------------------------------------------
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict:
    return {"app_version": VERSION, "ollama_model": normalize_model_name(OLLAMA_MODEL), "llm_active": USE_LLM}


@app.get("/ready")
def ready() -> JSONResponse:
    # Sans modèle de langage (USE_LLM=0), Ollama n'est pas exigé.
    reachable, present = ollama_status() if USE_LLM else (True, True)
    with lock:
        contracts = connection.execute("SELECT COUNT(*) FROM contrats").fetchone()[0]
    checks = {"database_loaded": contracts > 0, "classifier_loaded": classifier is not None,
              "interface_available": (STATIC / "index.html").exists(),
              "ollama_reachable": reachable, "ollama_model_available": present}
    # 200 si tout est prêt, 503 sinon : un outil de surveillance lit ce code.
    ok = all(checks.values())
    return JSONResponse({"status": "ready" if ok else "not_ready", "app_version": VERSION,
                         "ollama_model": normalize_model_name(OLLAMA_MODEL), "checks": checks},
                        status_code=200 if ok else 503)


@app.get("/api/polices")
def polices() -> list[dict]:
    with lock:
        # Une police, son contrat (assureur, pays) et ses options réunies en « opt1|opt2 ».
        rows = connection.execute(
            "SELECT p.*, c.assureur, c.pays, group_concat(o.option, '|') AS options FROM polices p "
            "JOIN contrats c ON c.gamme = p.gamme LEFT JOIN police_options o ON o.numero = p.numero "
            "GROUP BY p.numero ORDER BY p.numero").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/sinistres")
def sinistres() -> list[dict]:
    with lock:
        # Les sinistres saisis dans l'interface (WEB-...) ne sont pas proposés en démonstration.
        rows = connection.execute("SELECT * FROM sinistres WHERE id NOT LIKE 'WEB-%' ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/instruire")
def instruire_sinistre(demande: NouveauSinistre) -> dict:
    # Une instruction à la fois : la connexion SQLite est partagée.
    with lock:
        # Cas 1 : sinistre de démonstration, retrouvé par son numéro.
        if demande.sinistre_id:
            identifiant = demande.sinistre_id
            row = connection.execute("SELECT description FROM sinistres WHERE id = ?", (identifiant,)).fetchone()
            if row is None:
                raise HTTPException(404, f"sinistre inconnu : {identifiant}")
            description = row["description"]
        # Cas 2 : nouveau sinistre. Champs obligatoires et police vérifiés,
        # puis enregistrement dans la copie en mémoire.
        else:
            if not (demande.police and demande.description and demande.date_survenance):
                raise HTTPException(422, "police, description et date de survenance sont obligatoires")
            if connection.execute("SELECT 1 FROM polices WHERE numero = ?", (demande.police,)).fetchone() is None:
                raise HTTPException(404, f"police inconnue : {demande.police}")
            # Identifiant court et unique ; le préfixe WEB le distingue des démonstrations.
            identifiant = f"WEB-{uuid.uuid4().hex[:8]}"
            description = demande.description.strip()
            survenance = demande.date_survenance.isoformat()
            connection.execute(
                "INSERT INTO sinistres (id, numero_police, date_survenance, date_connaissance,"
                " date_declaration, description, bien, montant_estime) VALUES (?,?,?,?,?,?,?,?)",
                (identifiant, demande.police, survenance,
                 # Date de connaissance absente : date de survenance ; date de déclaration absente : aujourd'hui.
                 (demande.date_connaissance or demande.date_survenance).isoformat(),
                 (demande.date_declaration or date.today()).isoformat(),
                 description, demande.bien or None, demande.montant_estime))
            connection.commit()
        # Étape 1 : le classifieur prédit la ou les familles de garanties (vol, incendie...).
        prediction = predict(classifier, description)
        # Étape 2 : les 7 contrôles. Le modèle de langage n'est transmis que s'il est activé.
        instruction = instruire(connection, identifiant, prediction.families,
                                call_ollama if USE_LLM else None)
        # On rétablit l'accès aux colonnes par leur nom pour les requêtes suivantes.
        connection.row_factory = sqlite3.Row
    # Réponse lue par static/index.html ; seules les 3 familles les plus probables sont renvoyées.
    return {
        "sinistre": instruction.sinistre,
        "police": instruction.police,
        "contrat": {k: instruction.contrat[k] for k in ("code", "assureur", "pays", "produit", "reference")}
        if instruction.contrat else None,
        "familles": prediction.families,
        "probabilites": dict(list(prediction.probabilities.items())[:3]),
        "controles": [asdict(c) for c in instruction.controles],
        "verdict": instruction.verdict,
        "nature": instruction.nature,
        "indemnite": instruction.indemnite,
        "modele": normalize_model_name(OLLAMA_MODEL) if USE_LLM else None,
        "avertissement": WARNING,
    }
