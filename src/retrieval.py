# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : src/retrieval.py
# Auteur  : Thierry MBARGA
# Rôle    : choisir dans un contrat les clauses utiles à un sinistre
#           (définitions, garanties, conditions, exclusions).
# Méthode : synonymes métier, recherche BM25 (SQLite FTS5), bonus de famille,
#           composition par quotas.
# Entrée  : code du contrat, description, familles prédites.
# Sortie  : liste ordonnée de Clause, chacune avec la raison de son choix.
# ---------------------------------------------------------------------------
"""Recherche des clauses pertinentes pour un sinistre, dans un seul contrat.

Le contrat n'est jamais transmis en entier au LLM : on lui donne un petit
nombre de clauses choisies ainsi :

1. La description est réduite à ses termes significatifs, ramenés à leur
   racine et enrichis de **synonymes métier** (« vélo » → « bicyclette »,
   « local commun » → « parties communes », « bougie » → « incendie »,
   « chaleur »...). Les contrats n'emploient pas les mots de l'assuré.
2. Recherche plein texte BM25 (SQLite FTS5) dans les clauses du contrat.
3. Le score BM25 est renforcé pour les clauses des familles prédites par le
   classifieur.
4. Le contexte est **composé par quotas** : la clause d'**en-tête** de
   chaque garantie concernée (son étendue et, souvent, la formule ou
   l'option qu'elle suppose), des garanties et conditions, puis
   systématiquement des **exclusions** et des **définitions**. Une réponse
   qui ignorerait l'exclusion décisive serait fausse même si la garantie
   est bien trouvée.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from src.database import FAMILY_REGEX, normalize

# Mots vides : trop fréquents pour aider à trouver une clause.
STOP_WORDS = set("""
a afin ai aie aient ainsi alors au aucun aussi autre aux avais avait avant avec avez avoir
avons c ca car ce cela celle celui ces cet cette chez comme d dans de des deja depuis donc
du elle elles en encore est et etait ete etre eu fait faire il ils j je jusqu l la le les
leur leurs lui m ma mais me meme mes moi mon n ne ni nos notre nous on ont ou par pas
pendant peu peut plus pour pourquoi qu que quel quelle qui s sa sans se ses si son sont
sous suis sur t ta te tes toi ton tous tout toute tres tu un une vos votre vous y
bonjour madame monsieur merci hier matin soir nuit jour jours lundi semaine week end
ce matin svp urgent est-ce pris charge couvert assurance assure sinistre declare
""".split())

# Synonymes métier : mot de l'assuré → mots du contrat. Les clés et valeurs
# sont normalisées (sans accents) ; une valeur peut être une expression.
SYNONYMS = {
    "velo": ["bicyclette", "cycle", "mobilite durable", "engin de deplacement"],
    "trottinette": ["engin de deplacement", "mobilite durable"],
    "vole": ["vol"], "volee": ["vol"], "voles": ["vol"], "volees": ["vol"],
    "disparu": ["vol", "disparition"], "derobe": ["vol"], "plus la": ["vol"],
    "cambriole": ["vol", "effraction"], "force": ["effraction"],
    "local commun": ["locaux a usage commun", "parties communes", "local collectif"],
    "commun": ["parties communes", "usage commun"],
    "residence": ["immeuble", "parties communes"],
    "cave": ["dependances", "cave"], "garage": ["dependances", "garage"],
    "ferme a cle": ["serrure", "verrou", "fermees a cle"],
    "cle": ["serrure", "verrou", "cles"],
    "bougie": ["incendie", "flamme", "chaleur", "brulure", "eclairage"],
    "fondre": ["chaleur", "brulure", "fusion", "dommages menagers"],
    "fondu": ["chaleur", "brulure", "dommages menagers"],
    "brule": ["brulure", "incendie", "chaleur"],
    "table de jardin": ["mobilier de jardin", "meubles de jardin"],
    "jardin": ["mobilier de jardin", "meubles de jardin", "exterieur"],
    "terrasse": ["exterieur", "plein air", "terrasse"],
    "vacances": ["absence", "inoccupation"],
    "absent": ["absence", "inoccupation"],
    "fuite": ["degats des eaux", "conduites"],
    "vitre": ["bris de glace", "vitrage"],
    "tempete": ["tempete", "vent"],
    "voisin": ["tiers", "responsabilite civile"],
}

# Suffixes retirés pour obtenir une racine (« fermées » → « ferm »).
SUFFIXES = ("ements", "ement", "ations", "ation", "euses", "euse", "ees", "ee", "es", "e", "s")

# Quotas du contexte transmis au LLM.
# Nombre maximal de clauses par catégorie dans le contexte du modèle.
QUOTAS = {"entete": 2, "garantie_condition": 5, "exclusion": 5, "definition": 4}
FAMILY_BOOST = 1.5          # multiplicateur de score pour les familles prédites
CANDIDATES = 80             # nombre de clauses lues dans l'index avant tri


def stem(token: str) -> str:
    """Racine grossière : on retire un suffixe courant si le mot reste assez long."""
    for suffix in SUFFIXES:
        # Le suffixe n'est retiré que s'il reste au moins 4 lettres (racines trop courtes = ambiguës).
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def query_terms(description: str, use_synonyms: bool = True) -> list[str]:
    """Termes de recherche : mots significatifs de la description, puis
    synonymes métier (y compris pour les expressions de plusieurs mots)."""
    text = normalize(description)
    # Mots de plus de 2 lettres, hors mots vides ; dict.fromkeys supprime les doublons.
    tokens = [t for t in re.findall(r"[a-z]+", text) if t not in STOP_WORDS and len(t) > 2]
    terms = list(dict.fromkeys(tokens))
    if use_synonyms:
        for key, values in SYNONYMS.items():
            # \b : la clé doit être un mot entier (« cave » ne trouve pas « caveau »).
            if re.search(rf"\b{re.escape(key)}\b", text):
                terms.extend(values)
    return list(dict.fromkeys(terms))


def fts_query(terms: list[str]) -> str:
    """Requête FTS5 : chaque mot en préfixe de sa racine, chaque expression
    entre guillemets (recherche de phrase), le tout relié par OR."""
    parts = []
    for term in terms:
        words = term.split()
        if len(words) == 1:
            # « vol* » trouve vol, vols, volé... (recherche par préfixe).
            parts.append(f"{stem(words[0])}*")
        else:
            # Expression de plusieurs mots : recherche de la phrase exacte.
            parts.append('"' + " ".join(words) + '"')
    return " OR ".join(dict.fromkeys(parts))


# Une clause candidate : texte, familles, score et raison de sa sélection.
@dataclass
class Clause:
    id: int
    page: int
    section: str
    type: str
    text: str
    families: list[str] = field(default_factory=list)
    score: float = 0.0
    reason: str = ""

    def reference(self) -> str:
        return f"[{self.id}] p.{self.page} — {self.section}"


# BM25 de FTS5 est négatif (plus petit = meilleur) : on prend -bm25 comme score.
# BM25(q, j) = Σ_t idf(t) · tf(t,j)·(k1+1) / (tf(t,j) + k1·(1 − b + b·|j|/moy|j|)), k1 = 1,2, b = 0,75.
def _candidates(connection: sqlite3.Connection, contract_code: str, query: str) -> list[Clause]:
    rows = connection.execute(
        """SELECT a.id, a.page, a.section, a.type, a.texte, -bm25(articles_fts) AS score,
                  (SELECT group_concat(famille) FROM article_familles f WHERE f.article_id = a.id)
           FROM articles_fts
           JOIN articles a ON a.id = articles_fts.rowid
           JOIN contrats c ON c.id = a.contrat_id
           WHERE articles_fts MATCH ? AND c.code = ?
           ORDER BY bm25(articles_fts) LIMIT ?""",
        (query, contract_code, CANDIDATES)).fetchall()
    return [Clause(r[0], r[1], r[2], r[3], r[4], (r[6] or "").split(",") if r[6] else [], r[5])
            for r in rows]


def _definitions_for_terms(connection, contract_code: str, terms: list[str]) -> list[Clause]:
    """Définitions dont le terme défini correspond à la description ou à ses
    synonymes : toutes les racines du terme (au moins deux sur trois pour
    un terme de trois mots ou plus, « objets de mobilité durable »)."""
    rows = connection.execute(
        """SELECT d.terme_norm, a.id, a.page, a.section, a.type, a.texte
           FROM definitions d JOIN articles a ON a.id = d.article_id
           JOIN contrats c ON c.id = d.contrat_id WHERE c.code = ?""", (contract_code,)).fetchall()
    query_stems = {stem(word) for term in terms for word in term.split()}
    found = []
    for term, *article in rows:
        stems = [stem(w) for w in re.findall(r"[a-z]+", term) if w not in STOP_WORDS and len(w) > 2]
        if not stems:
            continue
        # Nombre de racines du terme défini retrouvées dans la description.
        matched = sum(s in query_stems for s in stems)
        needed = len(stems) if len(stems) < 3 else len(stems) - 1
        if matched >= needed:
            found.append(Clause(*article, reason=f"définition de « {term} »"))
    return found


def _guarantee_headers(connection, contract_code: str, families: list[str]) -> list[Clause]:
    """Première clause de la section de chaque garantie concernée (titre
    court contenant la famille, ex. « Vol », « Article 4 Vol et
    vandalisme ») : c'est là que le contrat dit ce qui est garanti et sous
    quelle formule ou option."""
    headers = []
    for family in families:
        regex = FAMILY_REGEX.get(family)
        if regex is None:
            continue
        rows = connection.execute(
            """SELECT a.id, a.page, a.section, a.type, a.texte, a.titre FROM articles a
               JOIN contrats c ON c.id = a.contrat_id
               WHERE c.code = ? AND a.type IN ('garantie', 'condition') ORDER BY a.rang""",
            (contract_code,)).fetchall()
        matching = [(article, title) for *article, title in rows
                    # Titre court (60 caractères au plus) qui nomme la famille : c'est un en-tête de garantie.
                    if len(title) <= 60 and regex.search(normalize(title))]
        # On préfère une section placée sous un titre de garanties (« Les
        # événements garantis », « Garanties optionnelles ») à un conseil
        # de prévention ou à une page d'introduction.
        in_guarantees = [m for m in matching if "garanti" in normalize(m[0][2])]
        for article, _ in (in_guarantees or matching)[:1]:
            headers.append(Clause(*article, families=[family],
                                  reason=f"en-tête de la garantie {family}"))
    return headers


def retrieve(connection: sqlite3.Connection, contract_code: str, description: str,
             families: list[str] | None = None, use_synonyms: bool = True,
             use_families: bool = True, quotas: dict | None = None) -> list[Clause]:
    """Clauses à transmettre au LLM, dans l'ordre : définitions, garanties et
    conditions, exclusions. Chaque clause porte la raison de sa sélection."""
    quotas = quotas or QUOTAS
    terms = query_terms(description, use_synonyms)
    if not terms:
        return []
    candidates = _candidates(connection, contract_code, fts_query(terms))
    families = families or []
    # Bonus : score × 1,5 pour une clause de la famille prédite par le classifieur.
    for clause in candidates:
        matched = [f for f in clause.families if f in families]
        if use_families and matched:
            clause.score *= FAMILY_BOOST
            clause.reason = f"famille {', '.join(matched)}"
        else:
            clause.reason = "recherche plein texte"
    candidates.sort(key=lambda c: -c.score)

    # Composition du contexte : en-têtes, définitions, puis remplissage par quotas
    # en prenant les meilleurs scores de chaque catégorie.
    selected: list[Clause] = []
    if use_families:
        selected += _guarantee_headers(connection, contract_code, families)[: quotas.get("entete", 0)]
    definitions = _definitions_for_terms(connection, contract_code, terms)[: quotas["definition"]]
    selected += definitions
    seen = {c.id for c in selected}
    buckets = {"garantie_condition": ("garantie", "condition"), "exclusion": ("exclusion",),
               "definition": ("definition",)}
    for bucket, kinds in buckets.items():
        already = sum(1 for c in selected if c.type in kinds and not c.reason.startswith("en-tête"))
        for clause in candidates:
            if already >= quotas[bucket]:
                break
            if clause.type in kinds and clause.id not in seen:
                selected.append(clause)
                seen.add(clause.id)
                already += 1
    # Ordre final : définitions, puis garanties et conditions, puis exclusions.
    order = {"definition": 0, "garantie": 1, "condition": 1, "exclusion": 2}
    return sorted(selected, key=lambda c: (order[c.type], -c.score))
