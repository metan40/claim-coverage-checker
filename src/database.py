"""Base SQLite des conditions générales.

Chaque contrat est découpé en passages par ``pdf_parsing.parse_contract``,
puis chaque passage est :

- typé (définition, exclusion, condition, garantie) par des règles lisibles ;
- rattaché à une ou plusieurs familles de garanties (vol, incendie...) ;
- indexé en plein texte (FTS5, classement BM25, accents ignorés).

Ajouter un contrat revient à déposer son PDF, ajouter une ligne au
catalogue (``data/conditions_generales/catalogue.csv``) et relancer
l'ingestion : aucun code n'est propre à un assureur.

Usage : ``python -m src.database`` (reconstruit ``db/contrats.sqlite``).
"""
from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "conditions_generales"
CATALOGUE = PDF_DIR / "catalogue.csv"
DB_PATH = ROOT / "db" / "contrats.sqlite"

ARTICLE_TYPES = ("definition", "exclusion", "condition", "garantie")

SCHEMA = """
CREATE TABLE contrats (
    id          INTEGER PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,    -- une version d'un contrat
    gamme       TEXT NOT NULL,           -- le produit, toutes versions confondues
    assureur    TEXT NOT NULL,
    pays        TEXT NOT NULL,
    produit     TEXT NOT NULL,
    reference   TEXT,
    version     TEXT,
    date_effet  TEXT NOT NULL,           -- AAAA-MM-JJ : début d'application de cette version
    source      TEXT,
    fichier     TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    pages       INTEGER
);
CREATE TABLE articles (
    id          INTEGER PRIMARY KEY,
    contrat_id  INTEGER NOT NULL REFERENCES contrats(id),
    rang        INTEGER NOT NULL,          -- ordre dans le document
    page        INTEGER NOT NULL,
    section     TEXT NOT NULL,             -- chemin des titres « A > B > C »
    titre       TEXT NOT NULL,             -- dernier titre du chemin
    type        TEXT NOT NULL CHECK (type IN ('definition','exclusion','condition','garantie')),
    texte       TEXT NOT NULL
);
CREATE TABLE article_familles (
    article_id  INTEGER NOT NULL REFERENCES articles(id),
    famille     TEXT NOT NULL,
    PRIMARY KEY (article_id, famille)
);
CREATE TABLE definitions (
    id          INTEGER PRIMARY KEY,
    contrat_id  INTEGER NOT NULL REFERENCES contrats(id),
    article_id  INTEGER NOT NULL REFERENCES articles(id),
    terme       TEXT NOT NULL,
    terme_norm  TEXT NOT NULL
);
CREATE TABLE decisions (
    id                INTEGER PRIMARY KEY,
    cree_le           TEXT NOT NULL DEFAULT (datetime('now')),
    contrat_id        INTEGER NOT NULL REFERENCES contrats(id),
    sinistre          TEXT NOT NULL,
    familles_predites TEXT,               -- JSON : famille -> probabilité
    verdict           TEXT CHECK (verdict IN ('potentiellement_couvert','potentiellement_exclu','indetermine')),
    reponse_json      TEXT,               -- réponse typée complète
    modele            TEXT,
    duree_secondes    REAL
);
CREATE INDEX idx_articles_contrat ON articles(contrat_id, type);
CREATE INDEX idx_familles ON article_familles(famille);
CREATE VIRTUAL TABLE articles_fts USING fts5(
    section, texte, content='articles', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
"""


def normalize(text: str) -> str:
    """Minuscules, sans accents, apostrophes et espaces uniformisés."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", text).strip()


# --- Typage des passages ---------------------------------------------------

DEFINITION_HEADINGS = re.compile(r"definition|lexique|glossaire")
EXCLUSION_HEADINGS = re.compile(
    r"exclu|qu'est-ce qui n'est pas|n'est pas (assure|garanti|couvert)|ne sont pas (assures|garantis|couverts)"
    r"|ce que nous ne (garantissons|couvrons)")
EXCLUSION_TEXT = re.compile(
    r"\b(sont(?: \w+){0,3} exclus|est(?: \w+){0,3} exclue?s?\b|nous ne (garantissons|couvrons|prenons en charge) pas"
    r"|nous n'intervenons pas|ne sont pas (garantis|assures|couverts|compris)"
    r"|n'est pas (garanti|assure|couvert)|ne garantissons pas|reste(nt)? exclus)")
CONDITION_HEADINGS = re.compile(r"condition|obligation|prevention|mesures? de (securite|protection)")
CONDITION_TEXT = re.compile(
    r"\b(a condition que|a condition qu'|sous reserve que|vous devez|vous etes tenu"
    r"|sous peine de|decheance|reduction de (l'indemnite|\d+ ?%)|regle proportionnelle)")


def article_type(section: str, text: str) -> str:
    """Type d'un passage. Le titre prime sur le texte ; l'ordre des tests
    reflète la priorité : une exclusion citée dans une définition reste une
    définition, une exclusion assortie d'une condition reste une exclusion.

    Les définitions et exclusions se lisent sur tout le chemin des titres
    (« Définitions > Incendie ») ; les conditions sur le dernier titre
    seulement, sinon « CONDITIONS GÉNÉRALES » qualifierait tout le contrat."""
    heading, body = normalize(section), normalize(text)
    last_heading = heading.rsplit(" > ", 1)[-1]
    if DEFINITION_HEADINGS.search(heading):
        return "definition"
    if EXCLUSION_HEADINGS.search(heading) or EXCLUSION_TEXT.search(body):
        return "exclusion"
    if CONDITION_HEADINGS.search(last_heading) or CONDITION_TEXT.search(body):
        return "condition"
    return "garantie"


# --- Familles de garanties -------------------------------------------------

FAMILY_PATTERNS = {
    "vol": r"\bvols?\b|cambriol|effraction|vandalism|tentative de vol",
    "incendie": r"incendie|explosion|foudre|fumee|combustion|brulure|roussi"
                r"|chaleur|dommages menagers|embrasement",
    "degats_des_eaux": r"degats? des eaux|fuite|infiltration|debordement|\bgel\b|canalisation",
    "bris_de_glace": r"bris de (glace|vitr)|vitrage|vitre|miroir",
    "evenements_naturels": r"tempete|grele|poids de la neige|inondation|catastrophe"
                           r"|tremblement de terre|glissement de terrain|attentat",
    "responsabilite_civile": r"responsabilite civile|recours des (voisins|tiers)|dommages causes aux tiers",
    "jardin": r"jardin|piscine|plein air|exterieur",
    "mobilite": r"velo|bicyclette|trottinette|mobilite|engins? de deplacement",
}
FAMILY_REGEX = {name: re.compile(pattern) for name, pattern in FAMILY_PATTERNS.items()}


def article_families(section: str, text: str) -> list[str]:
    """Familles d'un passage : toute famille présente dans le titre, ou citée
    au moins deux fois dans le texte. Un passage peut en avoir plusieurs
    (le vol de vélos relève de « vol » et de « mobilite »)."""
    heading, body = normalize(section), normalize(text)
    families = []
    for name, regex in FAMILY_REGEX.items():
        if regex.search(heading) or len(regex.findall(body)) >= 2:
            families.append(name)
    return families


# --- Ingestion ---------------------------------------------------------------

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_catalogue(path: Path = CATALOGUE) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def create_database(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    connection = sqlite3.connect(db_path)
    connection.executescript(SCHEMA)
    return connection


def insert_contract(connection: sqlite3.Connection, entry: dict, passages, pages: int,
                    sha256: str) -> int:
    cursor = connection.execute(
        "INSERT INTO contrats (code, gamme, assureur, pays, produit, reference, version,"
        " date_effet, source, fichier, sha256, pages) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (entry["code"], entry["gamme"], entry["assureur"], entry["pays"], entry["produit"],
         entry.get("reference"), entry.get("version"), entry["date_effet"], entry.get("source"),
         entry["fichier"], sha256, pages))
    contract_id = cursor.lastrowid
    previous = None
    for rank, passage in enumerate(passages):
        section = passage.section or "(sans titre)"
        title = next((h for h in reversed(passage.heading_path) if h), section)
        kind = article_type(section, passage.text)
        # Un passage coupé pour sa longueur hérite du type de son début :
        # la suite d'une liste d'exclusions reste une exclusion.
        if (previous and previous[0] == section and previous[1] in ("exclusion", "definition")
                and kind == "garantie"):
            kind = previous[1]
        cursor = connection.execute(
            "INSERT INTO articles (contrat_id, rang, page, section, titre, type, texte)"
            " VALUES (?,?,?,?,?,?,?)",
            (contract_id, rank, passage.page, section, title, kind, passage.text))
        article_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO article_familles (article_id, famille) VALUES (?,?)",
            [(article_id, family) for family in article_families(section, passage.text)])
        if kind == "definition" and passage.heading_path and title != passage.heading_path[0]:
            connection.execute(
                "INSERT INTO definitions (contrat_id, article_id, terme, terme_norm)"
                " VALUES (?,?,?,?)",
                (contract_id, article_id, title, normalize(title).rstrip(" :")))
        previous = (section, kind)
    return contract_id


def build_database(db_path: Path = DB_PATH, catalogue: Path = CATALOGUE) -> dict:
    """Reconstruit la base à partir du catalogue. Renvoie un résumé par contrat."""
    import pdfplumber

    from src.pdf_parsing import parse_contract

    connection = create_database(db_path)
    summary = {}
    try:
        for entry in read_catalogue(catalogue):
            pdf_path = catalogue.parent / entry["fichier"]
            with pdfplumber.open(pdf_path) as pdf:
                pages = len(pdf.pages)
            passages = parse_contract(pdf_path)
            insert_contract(connection, entry, passages, pages, _sha256(pdf_path))
            summary[entry["code"]] = len(passages)
        connection.execute("INSERT INTO articles_fts(articles_fts) VALUES ('rebuild')")
        connection.commit()
    finally:
        connection.close()
    return summary


def applicable_version(connection: sqlite3.Connection, gamme: str,
                       claim_date: str) -> sqlite3.Row | None:
    """Version du contrat applicable à la date du sinistre (AAAA-MM-JJ) : la
    plus récente dont la date d'effet précède le sinistre. Aucune version
    antérieure au sinistre : None (l'analyse doit alors le signaler)."""
    connection.row_factory = sqlite3.Row
    return connection.execute(
        "SELECT * FROM contrats WHERE gamme = ? AND date_effet <= ?"
        " ORDER BY date_effet DESC LIMIT 1", (gamme, claim_date)).fetchone()


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Connexion en lecture pour l'application."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


if __name__ == "__main__":
    for code, count in build_database().items():
        print(f"{code}: {count} passages")
    print(f"Base écrite : {DB_PATH}")
