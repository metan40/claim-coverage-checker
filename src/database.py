"""Base SQLite des conditions générales.

Chaque contrat est découpé en passages par ``pdf_parsing.parse_contract``,
puis chaque passage est :

- typé (définition, exclusion, condition, garantie) par des règles lisibles ;
- rattaché à une ou plusieurs familles de garanties (vol, incendie...) ;
- indexé en plein texte (FTS5, classement BM25, accents ignorés).

Ajouter un contrat revient à déposer son PDF, ajouter une ligne au
catalogue (``data/conditions_generales/catalogue.csv``) et relancer
l'ingestion : aucun code n'est propre à un assureur.

La base contient aussi les données structurées de l'instruction :

- le catalogue des garanties de chaque contrat (``data/garanties/garanties.csv``),
  relié à la clause qui le fonde ;
- un portefeuille de polices et leurs options, et des déclarations de
  sinistres (données de démonstration, ``data/portefeuille`` et
  ``data/sinistres/sinistres_demo.csv`` ; un portefeuille synthétique de
  grande taille s'ajoute avec ``python -m src.portefeuille``) ;
- les analyses et le détail de leurs contrôles (traçabilité) ;
- le journal des imports de contrats.

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
GARANTIES = ROOT / "data" / "garanties" / "garanties.csv"
POLICES_DEMO = ROOT / "data" / "portefeuille" / "polices_demo.csv"
SINISTRES_DEMO = ROOT / "data" / "sinistres" / "sinistres_demo.csv"
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
    pages       INTEGER,
    delai_declaration INTEGER,           -- délai contractuel de déclaration
    delai_vol   INTEGER,                 -- délai propre au vol
    unite_delai TEXT CHECK (unite_delai IN ('jours','jours_ouvres')),
    page_delais INTEGER
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
-- Catalogue des garanties : ce que propose chaque contrat, et à quelle condition.
CREATE TABLE garanties (
    id          INTEGER PRIMARY KEY,
    contrat_id  INTEGER NOT NULL REFERENCES contrats(id),
    code        TEXT NOT NULL,
    libelle     TEXT NOT NULL,
    famille     TEXT,                    -- famille d'événement (vide pour une extension de bien)
    statut      TEXT NOT NULL CHECK (statut IN ('base','formule','option','extension_bien')),
    formules    TEXT,                    -- formules qui l'incluent, séparées par |
    option      TEXT,                    -- option qui l'ajoute
    biens       TEXT,                    -- biens couverts par une extension, séparés par |
    plafond     REAL,                    -- plafond propre à la garantie (euros)
    page        INTEGER NOT NULL,
    article_id  INTEGER REFERENCES articles(id),   -- clause qui fonde la garantie
    validation  TEXT NOT NULL DEFAULT 'proposé',
    UNIQUE (contrat_id, code)
);
-- Portefeuille (conditions particulières).
CREATE TABLE polices (
    numero          TEXT PRIMARY KEY,
    gamme           TEXT NOT NULL,       -- produit ; la version applicable dépend de la date
    formule         TEXT NOT NULL,
    date_effet      TEXT NOT NULL,
    date_fin        TEXT,                -- vide tant que le contrat court
    plafond_contenu REAL NOT NULL,
    franchise       REAL NOT NULL,
    origine         TEXT NOT NULL DEFAULT 'demo' CHECK (origine IN ('demo','synthetique'))
);
CREATE TABLE police_options (
    numero      TEXT NOT NULL REFERENCES polices(numero),
    option      TEXT NOT NULL,
    PRIMARY KEY (numero, option)
);
-- Déclarations de sinistres.
CREATE TABLE sinistres (
    id                TEXT PRIMARY KEY,
    numero_police     TEXT NOT NULL REFERENCES polices(numero),
    date_survenance   TEXT NOT NULL,
    date_connaissance TEXT,              -- date à laquelle l'assuré a constaté le sinistre
    date_declaration  TEXT,
    description       TEXT NOT NULL,
    bien              TEXT,              -- catégorie du bien touché (velo, mobilier_jardin...)
    montant_estime    REAL
);
-- Instructions et détail des contrôles.
CREATE TABLE analyses (
    id              INTEGER PRIMARY KEY,
    cree_le         TEXT NOT NULL DEFAULT (datetime('now')),
    sinistre_id     TEXT NOT NULL REFERENCES sinistres(id),
    contrat_id      INTEGER REFERENCES contrats(id),
    familles        TEXT,                -- JSON : famille -> probabilité
    verdict         TEXT CHECK (verdict IN ('potentiellement_couvert','potentiellement_exclu','indetermine')),
    nature          TEXT,
    indemnite_estimee REAL,
    modele          TEXT,
    duree_secondes  REAL,
    avis_gestionnaire TEXT
);
CREATE TABLE controles (
    id          INTEGER PRIMARY KEY,
    analyse_id  INTEGER NOT NULL REFERENCES analyses(id),
    numero      INTEGER NOT NULL CHECK (numero BETWEEN 1 AND 7),
    nom         TEXT NOT NULL,
    statut      TEXT NOT NULL CHECK (statut IN ('satisfait','bloquant','a_verifier','sans_objet')),
    constat     TEXT NOT NULL,
    source      TEXT NOT NULL,
    article_id  INTEGER REFERENCES articles(id),
    question    TEXT
);
-- Journal des imports de contrats.
CREATE TABLE imports (
    id          INTEGER PRIMARY KEY,
    contrat_id  INTEGER NOT NULL REFERENCES contrats(id),
    date        TEXT NOT NULL DEFAULT (datetime('now')),
    duree_secondes REAL,
    clauses     INTEGER,
    definitions INTEGER,
    exclusions  INTEGER,
    conditions  INTEGER,
    garanties   INTEGER,
    statut      TEXT NOT NULL
);
CREATE INDEX idx_articles_contrat ON articles(contrat_id, type);
CREATE INDEX idx_polices_gamme ON polices(gamme);
CREATE INDEX idx_sinistres_police ON sinistres(numero_police);
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
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


def insert_contract(connection: sqlite3.Connection, entry: dict, passages, pages: int,
                    sha256: str) -> int:
    cursor = connection.execute(
        "INSERT INTO contrats (code, gamme, assureur, pays, produit, reference, version,"
        " date_effet, source, fichier, sha256, pages, delai_declaration, delai_vol, unite_delai,"
        " page_delais) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (entry["code"], entry["gamme"], entry["assureur"], entry["pays"], entry["produit"],
         entry.get("reference"), entry.get("version"), entry["date_effet"], entry.get("source"),
         entry["fichier"], sha256, pages, _int(entry.get("delai_declaration")),
         _int(entry.get("delai_vol")), entry.get("unite_delai") or None,
         _int(entry.get("page_delais"))))
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


def _int(value) -> int | None:
    return int(value) if value not in (None, "") else None


def _float(value) -> float | None:
    return float(value) if value not in (None, "") else None


def record_import(connection: sqlite3.Connection, contract_id: int, duration: float) -> None:
    """Journalise un import : nombre de clauses par type. Un import sans
    exclusion ni définition est suspect (découpage à contrôler)."""
    counts = dict(connection.execute(
        "SELECT type, count(*) FROM articles WHERE contrat_id = ? GROUP BY type", (contract_id,)))
    total = sum(counts.values())
    status = "ok" if counts.get("exclusion") and counts.get("definition") else "a_controler"
    connection.execute(
        "INSERT INTO imports (contrat_id, duree_secondes, clauses, definitions, exclusions,"
        " conditions, garanties, statut) VALUES (?,?,?,?,?,?,?,?)",
        (contract_id, round(duration, 2), total, counts.get("definition", 0),
         counts.get("exclusion", 0), counts.get("condition", 0), counts.get("garantie", 0), status))


def load_guarantees(connection: sqlite3.Connection, path: Path = GARANTIES) -> int:
    """Charge le catalogue des garanties et relie chaque garantie à la clause
    qui la fonde : la première clause de la bonne page contenant le fragment
    cité (dans le titre ou le texte). Une garantie dont la clause est
    introuvable est refusée : le catalogue doit rester vérifiable."""
    contracts = dict(connection.execute("SELECT code, id FROM contrats"))
    loaded = 0
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            contract_id = contracts.get(row["contrat"])
            if contract_id is None:
                continue
            found = connection.execute(
                "SELECT id FROM articles WHERE contrat_id = ? AND page = ?"
                " AND (section || ' ' || replace(texte, char(10), ' ')) LIKE ? ORDER BY rang LIMIT 1",
                (contract_id, int(row["page"]), f"%{row['fragment']}%")).fetchone()
            if found is None:
                raise ValueError(f"{row['contrat']} {row['code']} : fragment introuvable page {row['page']}")
            connection.execute(
                "INSERT INTO garanties (contrat_id, code, libelle, famille, statut, formules, option,"
                " biens, plafond, page, article_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (contract_id, row["code"], row["libelle"], row["famille"] or None, row["statut"],
                 row["formules"] or None, row["option"] or None, row["biens"] or None,
                 _float(row["plafond"]), int(row["page"]), found[0]))
            loaded += 1
    return loaded


def load_demo(connection: sqlite3.Connection, policies: Path = POLICES_DEMO,
              claims: Path = SINISTRES_DEMO) -> tuple[int, int]:
    """Charge les polices et sinistres de démonstration (données fictives)."""
    with policies.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        connection.execute(
            "INSERT INTO polices (numero, gamme, formule, date_effet, date_fin, plafond_contenu,"
            " franchise, origine) VALUES (?,?,?,?,?,?,?, 'demo')",
            (row["numero"], row["gamme"], row["formule"], row["date_effet"], row["date_fin"] or None,
             float(row["plafond_contenu"]), float(row["franchise"])))
        connection.executemany(
            "INSERT INTO police_options (numero, option) VALUES (?,?)",
            [(row["numero"], option) for option in row["options"].split("|") if option])
    with claims.open(encoding="utf-8") as handle:
        claim_rows = list(csv.DictReader(handle))
    for row in claim_rows:
        connection.execute(
            "INSERT INTO sinistres (id, numero_police, date_survenance, date_connaissance,"
            " date_declaration, description, bien, montant_estime) VALUES (?,?,?,?,?,?,?,?)",
            (row["id"], row["police"], row["date_survenance"], row["date_connaissance"] or None,
             row["date_declaration"] or None, row["description"], row["bien"] or None,
             _float(row["montant_estime"])))
    return len(rows), len(claim_rows)


def build_database(db_path: Path = DB_PATH, catalogue: Path = CATALOGUE) -> dict:
    """Reconstruit la base à partir du catalogue. Renvoie un résumé par contrat."""
    import time

    import pdfplumber

    from src.pdf_parsing import parse_contract

    connection = create_database(db_path)
    summary = {}
    try:
        for entry in read_catalogue(catalogue):
            start = time.perf_counter()
            pdf_path = catalogue.parent / entry["fichier"]
            with pdfplumber.open(pdf_path) as pdf:
                pages = len(pdf.pages)
            passages = parse_contract(pdf_path)
            contract_id = insert_contract(connection, entry, passages, pages, _sha256(pdf_path))
            record_import(connection, contract_id, time.perf_counter() - start)
            summary[entry["code"]] = len(passages)
        connection.execute("INSERT INTO articles_fts(articles_fts) VALUES ('rebuild')")
        summary["garanties"] = load_guarantees(connection)
        summary["polices"], summary["sinistres"] = load_demo(connection)
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
    for name, count in build_database().items():
        print(f"{name} : {count}")
    print(f"Base écrite : {DB_PATH}")
