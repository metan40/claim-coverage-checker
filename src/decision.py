"""Analyse de couverture : réponse typée du LLM, vérifiée par l'application.

Le LLM (local, via Ollama) lit la description du sinistre et les clauses
choisies par ``retrieval.py``. Il doit répondre dans un format JSON imposé :
verdict, clauses citées avec leur nature, conditions à vérifier,
informations manquantes.

L'application a ensuite le dernier mot :

- une clause citée doit faire partie des clauses fournies, et son extrait
  doit se retrouver dans le texte de la clause ; sinon elle est écartée ;
- un verdict sans clause vérifiée devient « indéterminé » ;
- « potentiellement couvert » est impossible si une exclusion vérifiée est
  citée, « potentiellement exclu » exige une exclusion, une condition ou une
  définition vérifiée ;
- les questions qu'un gestionnaire poserait (plainte, effraction, flammes
  ou simple chaleur, formule souscrite...) sont ajoutées par des règles
  explicites, sans dépendre du modèle.

Chaque règle appliquée est listée dans ``ajustements`` : l'utilisateur voit
ce que le modèle a dit et ce que l'application a corrigé.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Callable

from src.database import normalize
from src.retrieval import Clause

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "400"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")

VERDICTS = ("potentiellement_couvert", "potentiellement_exclu", "indetermine")
NATURES = ("garantie", "garantie_optionnelle", "condition", "exclusion", "definition",
           "reduction", "decheance", "plafond_franchise")
WARNING = ("Aide à la décision : cette analyse ne constitue pas une décision contractuelle. "
           "Seuls les conditions particulières, les pièces du dossier et le gestionnaire "
           "permettent de conclure.")
CLAUSE_CHARACTERS = 650      # texte de clause transmis au modèle
EXTRACT_MIN_OVERLAP = 0.8    # part des mots de l'extrait présents dans la clause

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "justification": {"type": "string"},
        "clauses": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "ref": {"type": "string"},
                "nature": {"type": "string", "enum": list(NATURES)},
                "extrait": {"type": "string"},
                "effet": {"type": "string"},
            },
            "required": ["ref", "nature", "extrait", "effet"]}},
        "conditions_a_verifier": {"type": "array", "items": {"type": "string"}},
        "informations_manquantes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "justification", "clauses", "conditions_a_verifier",
                 "informations_manquantes"],
}

SYSTEM = """Tu es un assistant de gestionnaire de sinistres en assurance habitation.
Tu dis si le sinistre est potentiellement couvert par le contrat, en t'appuyant UNIQUEMENT
sur les clauses fournies, numérotées C1, C2...
Règles :
- Cite les clauses décisives par leur numéro et recopie mot pour mot un court extrait (une phrase au plus).
- Une exclusion qui correspond au sinistre l'emporte sur une garantie.
- Si une garantie est optionnelle ou dépend de la formule souscrite, dis-le.
- Si les clauses ne permettent pas de conclure, réponds "indetermine" et dis ce qui manque.
  Un "indetermine" justifié vaut mieux qu'un verdict non justifié.
- Réponds en français, brièvement, au format JSON demandé."""

# Questions de gestionnaire ajoutées selon la famille de garantie.
CHECKLIST = {
    "vol": ["Une plainte a-t-elle été déposée ?",
            "Y a-t-il des traces d'effraction (porte, serrure, cadenas) ?",
            "Le local ou la pièce était-il fermé à clé ?",
            "Une facture ou une preuve de possession du bien peut-elle être fournie ?"],
    "incendie": ["Y a-t-il eu des flammes (embrasement) ou seulement de la chaleur ?",
                 "Quelle est la nature et la valeur du bien endommagé (facture) ?"],
    "degats_des_eaux": ["Quelle est l'origine exacte de l'eau (conduite, appareil, toiture, voisin) ?",
                        "La fuite a-t-elle été réparée ?"],
    "bris_de_glace": ["Quel est l'élément vitré exact (fenêtre, véranda, plaque de cuisson, miroir) ?"],
    "evenements_naturels": ["Un arrêté de catastrophe naturelle ou un relevé météo existe-t-il ?"],
    "responsabilite_civile": ["Qui est la victime et quel est son lien avec l'assuré ?",
                              "La victime a-t-elle formulé une réclamation ?"],
}
OPTIONAL_PATTERN = re.compile(
    r"uniquement si mention|si vous avez souscrit|garanties? optionnelle|option\b|"
    r"ne sont acquises que si|mentionnees? (sur|dans) vos conditions particulieres")


@dataclass
class CitedClause:
    ref: str
    article_id: int
    page: int
    section: str
    type: str                 # type en base (définition, exclusion...)
    nature: str               # nature selon le modèle
    extrait: str
    effet: str
    extrait_verifie: bool


@dataclass
class Decision:
    verdict: str
    verdict_modele: str | None
    justification: str
    clauses: list[CitedClause] = field(default_factory=list)
    conditions_a_verifier: list[str] = field(default_factory=list)
    informations_manquantes: list[str] = field(default_factory=list)
    ajustements: list[str] = field(default_factory=list)
    clauses_fournies: int = 0
    modele: str = OLLAMA_MODEL
    duree_secondes: float = 0.0
    avertissement: str = WARNING

    def to_dict(self) -> dict:
        return asdict(self)


# --- Prompt ------------------------------------------------------------------

def references(clauses: list[Clause]) -> dict[str, Clause]:
    return {f"C{i}": clause for i, clause in enumerate(clauses, start=1)}


def build_prompt(description: str, contract_label: str, clauses: list[Clause]) -> str:
    blocks = []
    for ref, clause in references(clauses).items():
        text = re.sub(r"\s+", " ", clause.text)[:CLAUSE_CHARACTERS]
        blocks.append(f"{ref} | {clause.type} | p.{clause.page} | {clause.section}\n{text}")
    return (f"{SYSTEM}\n\nContrat : {contract_label}\n\nClauses :\n\n" + "\n\n".join(blocks)
            + f"\n\nSinistre déclaré : {description}\n\nRéponse JSON :")


def call_ollama(prompt: str) -> str:
    payload = json.dumps({
        "model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": RESPONSE_SCHEMA,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"temperature": 0, "num_ctx": OLLAMA_NUM_CTX, "num_predict": OLLAMA_NUM_PREDICT},
    }).encode("utf-8")
    request = urllib.request.Request(OLLAMA_URL, data=payload,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))["response"]


# --- Vérification --------------------------------------------------------------

def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize(text))


def extract_is_in_clause(extract: str, clause_text: str) -> bool:
    """L'extrait figure-t-il dans la clause ? Inclusion exacte après
    normalisation, ou au moins 80 % de ses mots présents dans la clause
    (le modèle recopie parfois avec un mot de plus ou de moins)."""
    words = _words(extract)
    if len(words) < 3:
        return False
    if " ".join(words) in " ".join(_words(clause_text)):
        return True
    vocabulary = set(_words(clause_text))
    return sum(w in vocabulary for w in words) / len(words) >= EXTRACT_MIN_OVERLAP


def _parse(raw: str) -> dict:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("réponse JSON qui n'est pas un objet")
    return data


def _unique(items) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in items if item and item.strip()))


def verify(raw: dict, clauses: list[Clause], families: list[str]) -> Decision:
    """Transforme la réponse brute du modèle en décision vérifiée."""
    refs = references(clauses)
    adjustments: list[str] = []
    verdict_model = raw.get("verdict")
    verdict = verdict_model if verdict_model in VERDICTS else "indetermine"
    if verdict != verdict_model:
        adjustments.append(f"Verdict du modèle invalide ({verdict_model!r}) : indéterminé.")

    cited: list[CitedClause] = []
    for item in raw.get("clauses") or []:
        ref = str(item.get("ref", "")).strip().upper()
        clause = refs.get(ref)
        if clause is None:
            adjustments.append(f"Clause {ref or '?'} citée par le modèle mais non fournie : écartée.")
            continue
        extract = str(item.get("extrait", "")).strip()
        verified = extract_is_in_clause(extract, clause.text)
        if not verified:
            adjustments.append(f"Extrait de {ref} introuvable dans la clause : remplacé par le début du texte.")
            extract = re.sub(r"\s+", " ", clause.text)[:220]
        nature = item.get("nature") if item.get("nature") in NATURES else clause.type
        cited.append(CitedClause(ref, clause.id, clause.page, clause.section, clause.type, nature,
                                 extract, str(item.get("effet", "")).strip(), verified))

    verified_clauses = [c for c in cited if c.extrait_verifie]
    exclusions = [c for c in verified_clauses if c.type == "exclusion" or c.nature == "exclusion"]
    limiting = [c for c in verified_clauses
                if c.type in ("exclusion", "condition", "definition")
                or c.nature in ("exclusion", "condition", "definition", "decheance")]
    if verdict != "indetermine" and not verified_clauses:
        adjustments.append("Aucune clause citée n'a pu être vérifiée : verdict ramené à indéterminé.")
        verdict = "indetermine"
    elif verdict == "potentiellement_couvert" and exclusions:
        adjustments.append("Le modèle conclut à une couverture tout en citant une exclusion : "
                           "verdict ramené à indéterminé.")
        verdict = "indetermine"
    elif verdict == "potentiellement_exclu" and not limiting:
        adjustments.append("Le modèle conclut à une exclusion sans citer d'exclusion, de condition "
                           "ou de définition vérifiée : verdict ramené à indéterminé.")
        verdict = "indetermine"

    missing = list(raw.get("informations_manquantes") or [])
    conditions = list(raw.get("conditions_a_verifier") or [])
    optional = [c for c in clauses if c.reason.startswith("en-tête")
                and OPTIONAL_PATTERN.search(normalize(c.text))]
    for clause in optional:
        question = (f"La garantie « {clause.section.split(' > ')[-1]} » est-elle souscrite "
                    f"(conditions particulières, formule ou option) ? Voir p.{clause.page}.")
        missing.append(question)
        adjustments.append(f"Garantie optionnelle ou liée à la formule (p.{clause.page}) : "
                           "question ajoutée.")
    for family in families:
        missing.extend(CHECKLIST.get(family, []))

    return Decision(
        verdict=verdict, verdict_modele=verdict_model,
        justification=str(raw.get("justification", "")).strip(),
        clauses=cited, conditions_a_verifier=_unique(conditions),
        informations_manquantes=_unique(missing), ajustements=adjustments,
        clauses_fournies=len(clauses))


def analyse(description: str, contract_label: str, clauses: list[Clause], families: list[str],
            llm: Callable[[str], str] = call_ollama) -> Decision:
    """Analyse complète. Si le modèle est indisponible ou répond hors format,
    l'analyse reste utile : verdict indéterminé, clauses à lire, questions."""
    start = time.perf_counter()
    if not clauses:
        decision = verify({"verdict": "indetermine", "justification":
                           "Aucune clause pertinente trouvée dans ce contrat."}, [], families)
    else:
        try:
            decision = verify(_parse(llm(build_prompt(description, contract_label, clauses))),
                              clauses, families)
        except Exception as error:  # modèle indisponible, délai dépassé, JSON invalide
            decision = verify({"verdict": "indetermine", "justification":
                               "Analyse automatique indisponible : lire les clauses proposées."},
                              clauses, families)
            decision.ajustements.insert(0, f"Modèle indisponible ou réponse invalide ({type(error).__name__}).")
            decision.verdict_modele = None
    decision.duree_secondes = round(time.perf_counter() - start, 2)
    return decision


def record(connection: sqlite3.Connection, contract_id: int, description: str,
           probabilities: dict, decision: Decision) -> int:
    """Trace l'analyse dans la table ``decisions``."""
    cursor = connection.execute(
        "INSERT INTO decisions (contrat_id, sinistre, familles_predites, verdict, reponse_json,"
        " modele, duree_secondes) VALUES (?,?,?,?,?,?,?)",
        (contract_id, description, json.dumps(probabilities), decision.verdict,
         json.dumps(decision.to_dict(), ensure_ascii=False), decision.modele,
         decision.duree_secondes))
    connection.commit()
    return cursor.lastrowid
