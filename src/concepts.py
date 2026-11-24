# Auteur : Thierry MBARGA
"""Dictionnaire des concepts métier : mots de l'assuré, jargon, mots du contrat.

Fichier : ``data/concepts/concepts.csv``. Un **concept** est une notion du
contrat (« locaux à usage commun », « faute intentionnelle »...). Pour chacun :

* ``termes_assure`` : comment un assuré ou un gestionnaire le dit, jargon
  compris (« DDE », « cramé », « kot », « PNO ») ;
* ``termes_contrat`` : comment les conditions générales l'écrivent.

Deux usages :

1. **Recherche des clauses** : chaque concept reconnu dans la description
   ajoute ses termes du contrat à la requête BM25 (les contrats n'emploient
   pas les mots de l'assuré).
2. **Prompt du modèle de langage** : un lexique « mot de l'assuré → mot du
   contrat » est joint à chaque question fermée, pour que le modèle relie
   les faits aux clauses sans deviner.

En notation matricielle, le dictionnaire est une matrice binaire
C ∈ {0,1}^{|V|×|Γ|} (terme t, concept γ) ; le vecteur des concepts d'une
description est g = Cᵀx, où x indique les termes présents.

Le dictionnaire est une donnée : on l'enrichit sans toucher au code.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.database import normalize

CONCEPTS_PATH = Path(__file__).resolve().parent.parent / "data" / "concepts" / "concepts.csv"


@dataclass(frozen=True)
class Concept:
    code: str
    categorie: str
    libelle: str
    termes_assure: tuple[str, ...]
    termes_contrat: tuple[str, ...]


def _split(cell: str) -> tuple[str, ...]:
    return tuple(t.strip() for t in (cell or "").split("|") if t.strip())


@lru_cache(maxsize=4)
def load(path: Path = CONCEPTS_PATH) -> tuple[Concept, ...]:
    with path.open(encoding="utf-8") as handle:
        return tuple(Concept(r["concept"], r["categorie"], r["libelle"],
                             _split(r["termes_assure"]), _split(r["termes_contrat"]))
                     for r in csv.DictReader(handle))


def _pattern(term: str) -> re.Pattern:
    words = [re.escape(w) for w in re.findall(r"[a-z0-9]+", normalize(term))]
    return re.compile(r"\b" + r"\W+".join(words) + r"\b")


@lru_cache(maxsize=4)
def _compiled(path: Path = CONCEPTS_PATH) -> tuple[tuple[Concept, tuple[tuple[str, re.Pattern], ...]], ...]:
    return tuple((c, tuple((t, _pattern(t)) for t in c.termes_assure + (c.libelle,)))
                 for c in load(path))


def detect(description: str, path: Path = CONCEPTS_PATH) -> list[tuple[Concept, str]]:
    """Concepts reconnus dans la description, avec le terme qui les a déclenchés."""
    text = normalize(description)
    found = []
    for concept, patterns in _compiled(path):
        for term, pattern in patterns:
            if pattern.search(text):
                found.append((concept, term))
                break
    return found


def contract_terms(description: str, path: Path = CONCEPTS_PATH) -> list[str]:
    """Termes du contrat à ajouter à la requête de recherche (normalisés)."""
    terms = []
    for concept, _ in detect(description, path):
        terms += [normalize(t) for t in concept.termes_contrat]
    return list(dict.fromkeys(terms))


def lexicon(description: str, path: Path = CONCEPTS_PATH) -> str:
    """Lexique joint au prompt : une ligne par concept reconnu."""
    lines = [f"- « {term} » : {concept.libelle} ; dans un contrat : "
             + ", ".join(f"« {t} »" for t in concept.termes_contrat[:4])
             for concept, term in detect(description, path)]
    return "\n".join(lines)
