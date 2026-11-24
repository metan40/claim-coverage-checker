# Auteur : Thierry MBARGA
"""Contrôles d'interprétation (4, 5 et 6) : une question fermée par contrôle.

Les contrôles factuels (``instruction.py``) disent si la police couvre la
bonne garantie. Restent trois questions qui demandent de **lire** les
clauses face aux faits :

4. l'événement et le bien entrent-ils dans la garantie ? (garanties, définitions)
5. une exclusion s'applique-t-elle ? (exclusions)
6. les conditions de garantie sont-elles remplies ? (conditions)

Pour chacune, le modèle de langage reçoit **seulement** les clauses du type
utile, retrouvées par ``retrieval.py``, et doit répondre « oui », « non » ou
« incertain », en citant une clause et un extrait. L'application décide
ensuite du statut :

- une réponse tranchée exige un extrait **vérifié** dans la clause citée ;
  sinon le contrôle reste « à vérifier » ;
- une exclusion vérifiée rend le contrôle 5 **bloquant** ;
- une condition non remplie ne bloque pas : elle est « à vérifier », car
  la sanction suppose un lien avec le sinistre (Luxembourg, art. 18) ;
- si le modèle est indisponible, chaque contrôle reste « à vérifier » avec
  les clauses à lire et leurs pages : l'instruction reste utile.
"""
from __future__ import annotations

import json
import re
from typing import Callable

from src.decision import CHECKLIST, CLAUSE_CHARACTERS, call_ollama, extract_is_in_clause
from src.retrieval import Clause

REPONSES = ("oui", "non", "incertain")
SCHEMA = {
    "type": "object",
    "properties": {
        "reponse": {"type": "string", "enum": list(REPONSES)},
        "ref": {"type": "string"},
        "extrait": {"type": "string"},
        "explication": {"type": "string"},
        "information_manquante": {"type": "string"},
    },
    "required": ["reponse", "ref", "extrait", "explication", "information_manquante"],
}
# numéro -> (nom, types de clauses utiles, question posée au modèle)
CONTROLES = {
    4: ("Événement et bien garantis", ("garantie", "definition"),
        "L'événement décrit ET le bien touché entrent-ils dans ce que les clauses garantissent ?"),
    5: ("Exclusions", ("exclusion",),
        "Une des exclusions fournies s'applique-t-elle à ce sinistre ?"),
    6: ("Conditions de garantie", ("condition",),
        "Les conditions de garantie fournies (fermeture, protection, prévention) sont-elles remplies ?"),
}
# Statut selon la réponse vérifiée : (oui, non)
STATUTS = {4: ("satisfait", "bloquant"), 5: ("bloquant", "satisfait"), 6: ("satisfait", "a_verifier")}
MAX_CLAUSES = 6

CONSIGNES = """Tu es un assistant de gestionnaire de sinistres en assurance habitation.
Réponds à UNE question fermée, en t'appuyant uniquement sur les clauses fournies (C1, C2...).
- Réponds « oui » ou « non » seulement si une clause le permet ; recopie alors mot pour mot
  un court extrait de cette clause (une phrase au plus) et donne sa référence.
- Si les faits ne suffisent pas, réponds « incertain » et indique l'information manquante.
- N'invente aucune clause. Réponds en JSON."""


def selection(clauses: list[Clause], numero: int) -> list[Clause]:
    """Clauses du type utile au contrôle, dans l'ordre de pertinence."""
    types = CONTROLES[numero][1]
    return [c for c in clauses if c.type in types][:MAX_CLAUSES]


def prompt(numero: int, description: str, faits: str, clauses: list[Clause]) -> str:
    blocs = []
    for i, clause in enumerate(clauses, start=1):
        texte = re.sub(r"\s+", " ", clause.text)[:CLAUSE_CHARACTERS]
        blocs.append(f"C{i} | {clause.type} | p.{clause.page} | {clause.section}\n{texte}")
    return (f"{CONSIGNES}\n\nClauses :\n\n" + "\n\n".join(blocs)
            + f"\n\nSinistre déclaré : {description}\nFaits connus : {faits}"
            + f"\n\nQuestion : {CONTROLES[numero][2]}\nRéponse JSON :")


def _pages(clauses: list[Clause]) -> str:
    return ", ".join(sorted({f"p.{c.page}" for c in clauses}, key=lambda p: int(p[2:])))


def interpreter(numero: int, description: str, faits: str, clauses: list[Clause],
                familles: list[str], llm: Callable | None = call_ollama):
    """Contrôle 4, 5 ou 6. Renvoie un ``instruction.Controle``."""
    from src.instruction import Controle   # import local : instruction importe ce module

    nom = CONTROLES[numero][0]
    utiles = selection(clauses, numero)
    questions = [q for f in familles for q in CHECKLIST.get(f, [])] if numero != 5 else []
    question = questions[0] if questions else None
    if not utiles:
        statut = "satisfait" if numero == 5 else "a_verifier"
        constat = ("Aucune exclusion pertinente retrouvée dans ce contrat." if numero == 5
                   else "Aucune clause de ce type retrouvée pour ce sinistre.")
        return Controle(numero, nom, statut, constat, "Conditions générales", question)
    source = f"Conditions générales {_pages(utiles)}"
    if llm is None:
        return Controle(numero, nom, "a_verifier",
                        f"{len(utiles)} clause(s) à lire ({_pages(utiles)}).", source, question)
    try:
        brut = json.loads(llm(prompt(numero, description, faits, utiles), SCHEMA))
    except Exception as erreur:          # modèle indisponible, délai dépassé, JSON invalide
        return Controle(numero, nom, "a_verifier",
                        f"Modèle indisponible ({type(erreur).__name__}) : {len(utiles)} clause(s) à lire "
                        f"({_pages(utiles)}).", source, question)
    reponse = brut.get("reponse") if brut.get("reponse") in REPONSES else "incertain"
    refs = {f"C{i}": c for i, c in enumerate(utiles, start=1)}
    clause = refs.get(str(brut.get("ref", "")).strip().upper())
    extrait = str(brut.get("extrait", "")).strip()
    explication = str(brut.get("explication", "")).strip()
    manque = str(brut.get("information_manquante", "")).strip() or question
    if reponse == "incertain":
        return Controle(numero, nom, "a_verifier", f"Le modèle ne peut pas conclure. {explication}".strip(),
                        source, manque)
    if clause is None or not extract_is_in_clause(extrait, clause.text):
        return Controle(numero, nom, "a_verifier",
                        f"Réponse « {reponse} » sans citation vérifiable : écartée. Clauses à lire "
                        f"({_pages(utiles)}).", source, manque)
    statut = STATUTS[numero][0 if reponse == "oui" else 1]
    constat = f"« {extrait} » — {explication}".rstrip(" —")
    return Controle(numero, nom, statut, constat, f"Conditions générales p.{clause.page}",
                    manque if statut == "a_verifier" else None, clause.id, clause.page)
