# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : src/pdf_parsing.py
# Auteur  : Thierry MBARGA
# Rôle    : découper un PDF de conditions générales en passages citables
#           (texte, page, chemin des titres), pour tout assureur.
# Méthode : pdfplumber (mots, police, taille), détection des colonnes,
#           des titres par la typographie, nettoyage des en-têtes répétés.
# Entrée  : chemin du PDF.  Sortie : liste de Passage.
# ---------------------------------------------------------------------------
"""Découpage générique de conditions générales PDF en passages citables.

Un seul code pour tous les contrats : c'est la condition pour « tenir des
centaines de contrats ». Le découpeur ne connaît aucun assureur ; il s'appuie
sur trois signaux présents dans presque tous les PDF de conditions générales :

1. la mise en page : une page est lue colonne par colonne lorsque le texte
   est réparti sur deux colonnes (lire ligne à ligne mélangerait les clauses) ;
2. la typographie : un titre est plus grand ou plus gras que le corps du
   texte, qui est estimé automatiquement (taille de police la plus fréquente) ;
3. la structure : chaque passage garde son chemin de titres (chapitre >
   section), sa page et sa colonne, pour pouvoir être cité.

Pièges rencontrés et traités :
* texte à lettres espacées (« V o s c o nt a ct s » chez Sogessur) :
  reconstitué avec une tolérance proportionnelle à la taille de la police ;
* en-têtes et pieds de page (« Assurance Habitation », « Page 17 ») :
  supprimés lorsqu'ils sont dans les marges et se répètent ;
* sommaires : une page dont la plupart des lignes se terminent ou commencent
  par un numéro de page est ignorée (sinon ses lignes passent pour des titres) ;
* texte décoratif en très petite police (logos, texte vertical) : ignoré ;
* longues sections : redécoupées en passages d'environ 900 caractères,
  aux frontières de puces ou de phrases, sans perdre le titre.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

# Réglages du découpage (en points PDF ou en caractères).
MAX_PASSAGE_CHARACTERS = 900
MIN_PASSAGE_CHARACTERS = 120
X_TOLERANCE_RATIO = 0.35   # écart entre lettres relatif à la taille de police
Y_TOLERANCE = 3
MIN_FONT_SIZE = 6.0        # en dessous : logos, texte vertical, mentions décoratives
MARGIN_TOP = 0.09          # part de la page considérée comme en-tête
MARGIN_BOTTOM = 0.94       # au-delà : pied de page
MAX_HEADING_LEVELS = 4
# Début de puce : symbole, « 1. », « 2) », « a) »...
BULLET_PATTERN = re.compile(r"^\s*(?:[•■▪●◦\-–]|\d+[.)]|[a-z][.)])\s+")


# Une ligne lue dans le PDF, avec sa taille de police et son gras.
@dataclass
class Line:
    page: int
    column: int
    top: float
    text: str
    size: float
    bold: bool
    in_margin: bool = False


@dataclass
class Passage:
    """Unité de recherche et de citation."""

    page: int
    heading_path: list[str]
    text: str
    lines: list[int] = field(default_factory=list)

    @property
    def section(self) -> str:
        return " > ".join(self.heading_path) if self.heading_path else "(sans titre)"


# ---------------------------------------------------------------------------
# 1. Lecture des lignes, colonne par colonne
# ---------------------------------------------------------------------------

def _group_rows(words) -> list[list]:
    """Regroupe les mots en lignes : un mot rejoint la ligne courante si son
    haut est à moins de Y_TOLERANCE du premier mot de la ligne (les puces,
    souvent décalées de 1 à 2 points, restent sur leur ligne)."""
    rows: list[list] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and word["top"] - rows[-1][0]["top"] <= Y_TOLERANCE:
            rows[-1].append(word)
        else:
            rows.append([word])
    return rows


def column_gutter(words, width: float) -> float | None:
    """Abscisse de la gouttière centrale si la page a deux colonnes, sinon None.

    On cherche, près du milieu, une verticale que presque aucune ligne ne
    traverse alors qu'une part importante des lignes se trouve entièrement
    à sa gauche et une autre entièrement à sa droite. Dans un texte sur une
    seule colonne, les lignes pleines traversent le milieu et presque
    aucune ne commence à droite ; entre deux colonnes, c'est l'inverse."""
    if len(words) < 40:
        return None
    rows = _group_rows(words)
    best = None
    # On teste chaque verticale x entre 40 % et 60 % de la largeur, tous les 2 points.
    for x in range(int(width * 0.4), int(width * 0.6), 2):
        crossed = left_only = right_only = 0
        for row in rows:
            if any(w["x0"] - 1 <= x <= w["x1"] + 1 for w in row):
                crossed += 1
            elif all(w["x1"] < x for w in row):
                left_only += 1
            elif all(w["x0"] > x for w in row):
                right_only += 1
        # Gouttière : au plus 5 % des lignes la traversent, au moins 20 % de lignes
        # entièrement à gauche et 20 % entièrement à droite.
        if (crossed <= 0.05 * len(rows) and left_only >= 0.2 * len(rows)
                and right_only >= 0.2 * len(rows)):
            if best is None or crossed < best[0]:
                best = (crossed, x)
    return None if best is None else float(best[1])


# Transforme des mots en lignes : taille médiane et gras (plus de 60 % des mots en gras).
def _words_to_lines(words, page_number: int, column: int, height: float) -> list[Line]:
    lines = []
    for row in _group_rows(words):
        row = sorted(row, key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in row).strip()
        if not text:
            continue
        sizes = [w["size"] for w in row]
        # Le gras se lit dans le nom de la police (« Arial-Bold », « Helvetica-Black »).
        bold_share = sum("bold" in w["fontname"].lower() or "black" in w["fontname"].lower()
                         for w in row) / len(row)
        top = row[0]["top"]
        lines.append(Line(page_number, column, top, text,
                          round(statistics.median(sizes), 1), bold_share > 0.6,
                          in_margin=top < MARGIN_TOP * height or top > MARGIN_BOTTOM * height))
    return lines


# Lit toutes les pages du PDF et renvoie les lignes dans l'ordre de lecture.
def read_lines(pdf_path: Path) -> list[Line]:
    lines: list[Line] = []
    with pdfplumber.open(pdf_path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(x_tolerance_ratio=X_TOLERANCE_RATIO,
                                       y_tolerance=Y_TOLERANCE,
                                       extra_attrs=["fontname", "size"])
            # Texte en police de moins de 6 points écarté (logos, mentions verticales).
            words = [w for w in words if w["size"] >= MIN_FONT_SIZE]
            height = page.height
            middle = column_gutter(words, page.width)
            # Deux colonnes : la colonne de gauche est lue en entier avant celle de droite.
            if middle is not None:
                left = [w for w in words if w["x0"] < middle]
                right = [w for w in words if w["x0"] >= middle]
                page_lines = (_words_to_lines(left, number, 1, height)
                              + _words_to_lines(right, number, 2, height))
            else:
                page_lines = _words_to_lines(words, number, 1, height)
            # Couverture : page 1 avec moins de 150 mots, ignorée.
            is_cover = number == 1 and len(words) < 150
            if not is_cover and not is_table_of_contents(page_lines):
                lines += page_lines
    return lines


def is_table_of_contents(page_lines: list[Line]) -> bool:
    """Sommaire : la majorité des lignes commencent ou finissent par un numéro de page."""
    body = [line for line in page_lines if not line.in_margin]
    if len(body) < 8:
        return False
    # Ligne numérotée : se termine par un numéro (« Vol ....... 12 ») ou commence par un numéro.
    numbered = sum(bool(re.search(r"(\s|\.)\d{1,3}$|^\d{1,3}\s+\D", line.text)) for line in body)
    titled = any(re.search(r"(table des mati|sommaire)", line.text, re.I) for line in body)
    return numbered / len(body) > 0.45 or (titled and numbered / len(body) > 0.25)


# ---------------------------------------------------------------------------
# 2. Nettoyage : en-têtes et pieds de page répétés
# ---------------------------------------------------------------------------

# Chiffres remplacés par # : « Page 3 » et « Page 17 » deviennent la même ligne.
def _normalize_repeated(text: str) -> str:
    return re.sub(r"\d+", "#", text.lower()).strip()


def remove_running_headers(lines: list[Line], page_count: int) -> list[Line]:
    """Supprime les lignes de marge répétées, et toute ligne répétée sur un
    quart des pages (référence du document, nom du produit…)."""
    margin_counts = Counter(_normalize_repeated(l.text) for l in lines if l.in_margin)
    # Une ligne répétée n'est un en-tête que si elle revient au même endroit
    # de la page : « CE QUI EST EXCLU », répété partout mais à des hauteurs
    # variables, est un vrai titre.
    all_counts = Counter((_normalize_repeated(l.text), round(l.top / 20)) for l in lines)
    # Répétée sur au moins un quart des pages (3 au minimum) = en-tête ou pied de page.
    threshold = max(3, page_count // 4)
    kept = []
    for line in lines:
        key = _normalize_repeated(line.text)
        if line.in_margin and margin_counts[key] >= 3:
            continue
        if all_counts[(key, round(line.top / 20))] >= threshold and len(key) < 90:
            continue
        # Numéro de page seul (« 17 », « Page 17 ») : supprimé.
        if re.fullmatch(r"(page\s*)?\d{1,3}\s*\|?", line.text.strip(), re.I):
            continue
        kept.append(line)
    return kept


# ---------------------------------------------------------------------------
# 3. Titres et passages
# ---------------------------------------------------------------------------

# Taille du corps de texte = taille de police la plus fréquente.
def body_font_size(lines: list[Line]) -> float:
    return Counter(line.size for line in lines).most_common(1)[0][0]


SYMBOL_BULLET = re.compile(r"^\s*(?:[•■▪●◦\-–]|[a-z][.)])\s+")


def heading_sizes(lines: list[Line], body_size: float) -> list[float]:
    """Tailles de titres de la plus grande à la plus petite. Les tailles
    proches (moins de 1,5 pt d'écart) forment un même niveau."""
    counts = Counter(line.size for line in lines
                     # Candidats titres : au moins 0,8 point de plus que le corps, 90 caractères au plus,
                     # taille vue au moins 2 fois.
                     if line.size >= body_size + 0.8 and len(line.text) <= 90)
    sizes = sorted((s for s, n in counts.items() if n >= 2), reverse=True)
    levels: list[float] = []
    for size in sizes:
        if not levels or levels[-1] - size >= 1.5:
            levels.append(size)
    return levels


# Niveau d'un titre d'après sa taille (1 = la plus grande).
def _size_level(size: float, levels: list[float]) -> int:
    for rank, level_size in enumerate(levels, start=1):
        if size >= level_size - 0.75:
            return rank
    return max(len(levels), 1)


def heading_level(line: Line, body_size: float, sizes: list[float] | None = None,
                  next_line: Line | None = None) -> int | None:
    """Niveau de titre (1 = le plus haut) ou None pour le corps de texte.

    * Titre par la taille : plus grand que le corps.
    * Titre par le gras, à la taille du corps : court, commençant par une
      majuscule ou un numéro, et pas suivi d'une autre ligne en gras qui le
      prolonge (sinon c'est une phrase en gras du corps, souvent une
      exclusion importante, qui doit rester du contenu).
    """
    sizes = sizes or []
    text = line.text.strip()
    # Trop long, trop court, finissant par une virgule ou une puce : pas un titre.
    if len(text) > 90 or len(text) < 3 or text.endswith((",", ";")) or SYMBOL_BULLET.match(text):
        return None
    if not re.search(r"[A-Za-zÀ-ÿ]{3}", text):
        return None
    if line.size >= body_size + 0.8:
        return min(_size_level(line.size, sizes), MAX_HEADING_LEVELS)
    if line.bold or (text.isupper() and len(text.split()) <= 8):
        if text[:1].islower() or len(text.split()) > 10:
            return None
        continues = (next_line is not None and next_line.bold
                     and next_line.size == line.size and next_line.page == line.page
                     and not text.endswith((":", "?", "."))
                     and next_line.text[:1].islower())
        if continues:
            return None
        return min(len(sizes) + 1, MAX_HEADING_LEVELS)
    return None


def _continues_sentence(previous: Line | None, line: Line) -> bool:
    """Vrai si ``line`` prolonge la phrase en gras de la ligne précédente
    (même bloc, phrase non terminée) : « … partenaire d'un Pacte » puis
    « Civil de solidarité (PACS) » n'est pas un titre."""
    return (previous is not None and previous.bold and line.bold
            and previous.page == line.page and previous.column == line.column
            and abs(previous.size - line.size) < 0.5
            and 0 < line.top - previous.top < 1.6 * line.size
            and not previous.text.rstrip().endswith((".", ":", "?", "!", ")")))


# Parcourt les lignes : un titre ferme le passage en cours et met à jour
# le chemin des titres ; une ligne de corps s'ajoute au passage en cours.
def build_passages(lines: list[Line]) -> list[Passage]:
    body = body_font_size(lines)
    sizes = heading_sizes(lines, body)
    passages: list[Passage] = []
    path: list[str] = []
    buffer: list[str] = []
    buffer_page = lines[0].page if lines else 1
    previous_was_heading = False
    previous_heading: Line | None = None

    # Termine le passage en cours (redécoupé s'il est trop long).
    def flush():
        nonlocal buffer
        text = " ".join(buffer).strip()
        if text:
            passages.extend(_split_long(Passage(buffer_page, list(path), text)))
        buffer = []

    for position, line in enumerate(lines):
        next_line = lines[position + 1] if position + 1 < len(lines) else None
        level = heading_level(line, body, sizes, next_line)
        previous_line = lines[position - 1] if position else None
        if (level is not None and not previous_was_heading and line.size < body + 0.8
                and _continues_sentence(previous_line, line)):
            level = None     # fin d'une phrase en gras commencée à la ligne précédente
        if level is not None:
            flush()
            title = line.text.strip()
            # Titre sur deux lignes : même niveau, même colonne, ligne juste en dessous.
            same_block = (previous_heading is not None and previous_was_heading
                          and previous_heading.page == line.page
                          and previous_heading.column == line.column
                          and abs(previous_heading.size - line.size) < 0.5
                          and 0 < line.top - previous_heading.top < 1.8 * line.size)
            if path and len(path) == level and (same_block or (previous_was_heading
                                                               and title[:1].islower())):
                path[-1] = f"{path[-1]} {title}"
            else:
                # Titre resté sans texte et suivi d'un titre de même niveau ou
                # plus haut : c'est une entrée de liste (« 3.2. La combustion
                # sans flamme »), qu'on conserve comme passage.
                if (previous_was_heading and previous_heading is not None and path
                        and level <= len(path) and path[-1]):
                    passages.append(Passage(previous_heading.page, list(path), path[-1]))
                # Le chemin garde les titres des niveaux supérieurs et remplace ceux du même niveau.
                path = path[: level - 1] + [title]
                while len(path) < level:     # niveau intermédiaire absent
                    path.insert(len(path) - 1, "")
            previous_was_heading = True
            previous_heading = line
            continue
        previous_was_heading = False
        if not buffer:
            buffer_page = line.page
        # Une puce commence une nouvelle ligne logique.
        if BULLET_PATTERN.match(line.text) and buffer:
            buffer.append("\n" + line.text.strip())
        else:
            buffer.append(line.text.strip())
    flush()
    for passage in passages:
        passage.heading_path = [title for title in passage.heading_path if title]
    return _merge_small(passages)


# Nettoyage du texte : césures, espaces multiples, retours à la ligne.
def _clean(text: str) -> str:
    text = re.sub(r"-\s+(?=[a-zà-ÿ])", "", text)        # césures de fin de ligne
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


# Passage de plus de 900 caractères : coupé aux puces ou aux fins de phrase.
def _split_long(passage: Passage) -> list[Passage]:
    text = _clean(passage.text)
    if len(text) <= MAX_PASSAGE_CHARACTERS:
        return [Passage(passage.page, passage.heading_path, text)]
    pieces, current = [], ""
    units = re.split(r"(?<=\n)|(?<=[.;:])\s+(?=[A-ZÀ-Ý•■\-])", text)
    for unit in units:
        if current and len(current) + len(unit) > MAX_PASSAGE_CHARACTERS:
            pieces.append(current.strip())
            current = ""
        current += unit if unit.endswith("\n") else unit + " "
    if current.strip():
        pieces.append(current.strip())
    return [Passage(passage.page, passage.heading_path, piece) for piece in pieces]


# Passage de moins de 120 caractères : fusionné avec le précédent s'il a le même titre.
def _merge_small(passages: list[Passage]) -> list[Passage]:
    merged: list[Passage] = []
    for passage in passages:
        if (merged and len(passage.text) < MIN_PASSAGE_CHARACTERS
                and merged[-1].heading_path == passage.heading_path
                and len(merged[-1].text) + len(passage.text) <= MAX_PASSAGE_CHARACTERS):
            merged[-1].text += "\n" + passage.text
        else:
            merged.append(passage)
    return merged


# Point d'entrée : lecture, nettoyage, puis construction des passages.
def parse_contract(pdf_path: Path) -> list[Passage]:
    lines = read_lines(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
    return build_passages(remove_running_headers(lines, page_count))
