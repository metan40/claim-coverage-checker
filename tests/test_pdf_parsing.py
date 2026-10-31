"""Tests du découpage des PDF, sur des données synthétiques (sans PDF)."""
from src.pdf_parsing import (Line, _continues_sentence, build_passages, column_gutter,
                             heading_level, remove_running_headers)


def _word(text, x0, top, width=40):
    return {"text": text, "x0": x0, "x1": x0 + width, "top": top, "size": 9, "fontname": "Arial"}


def test_two_columns_detected():
    words = []
    for row in range(30):
        words.append(_word("gauche", 50, row * 12))
        words.append(_word("texte", 100, row * 12))
        words.append(_word("droite", 320, row * 12 + 5))
        words.append(_word("texte", 370, row * 12 + 5))
    gutter = column_gutter(words, 595)
    assert gutter is not None and 140 < gutter < 320


def test_single_column_with_full_lines_not_split():
    words = []
    for row in range(30):
        x = 50 + (row % 3) * 7          # coupures de mots à des endroits variables
        while x < 540:
            words.append(_word("mot", x, row * 12, width=33))
            x += 37
    assert column_gutter(words, 595) is None


def _line(text, top=100, size=9.0, bold=False, page=1, in_margin=False):
    return Line(page, 1, top, text, size, bold, in_margin)


def test_heading_by_size_and_by_bold():
    assert heading_level(_line("Vol", size=14), 9.0, [14.0]) == 1
    assert heading_level(_line("CE QUI EST EXCLU", bold=True), 9.0, [14.0]) == 2
    assert heading_level(_line("le vol commis par effraction", bold=True), 9.0, [14.0]) is None


def test_bold_sentence_continuation_is_not_a_heading():
    previous = _line("• Le vol commis par vos locataires, partenaire d'un Pacte", top=100, bold=True)
    line = _line("Civil de solidarité (PACS), ascendants et descendants.", top=110, bold=True)
    assert _continues_sentence(previous, line)
    finished = _line("CE QUI EST EXCLU :", top=100, bold=True)
    assert not _continues_sentence(finished, line)


def test_running_headers_removed_but_repeated_titles_kept():
    lines = []
    for page in range(1, 9):
        lines.append(_line("Assurance Habitation", top=20, page=page, in_margin=True))
        lines.append(_line("CE QUI EST EXCLU", top=100 + page * 60, bold=True, page=page))
        lines.append(_line(f"Texte de la page {page}.", top=130 + page * 60, page=page))
    kept = {line.text for line in remove_running_headers(lines, 8)}
    assert "Assurance Habitation" not in kept
    assert "CE QUI EST EXCLU" in kept


def test_passages_keep_heading_path():
    lines = [
        _line("Vol", top=50, size=14),
        _line("CE QUI EST EXCLU", top=70, bold=True),
        _line("Les vols des biens déposés dans les locaux à usage commun "
              "des occupants de l'immeuble, quelle que soit la formule souscrite.", top=85),
        _line("Le vol commis sans effraction ni escalade ni usage de fausses clés "
              "lorsque le logement est inoccupé.", top=97),
    ] + [_line(f"Texte courant numéro {i} du contrat.", top=200 + i * 12) for i in range(20)] + [
        _line("Incendie", top=500, size=14),
        _line("Texte de la garantie incendie, assez long pour former un passage.", top=520),
    ]
    passages = build_passages(lines)
    assert passages[0].heading_path == ["Vol", "CE QUI EST EXCLU"]
    assert "locaux à usage commun" in passages[0].text
