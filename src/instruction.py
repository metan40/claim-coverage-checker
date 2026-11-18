"""Instruction d'un sinistre en sept contrôles.

Un gestionnaire instruit un sinistre selon une suite de contrôles, du plus
simple au plus fin. Ce module réalise les contrôles **factuels**, exacts et
auditables, par des requêtes SQL sur le portefeuille, la déclaration et le
catalogue des garanties :

1. contrat en vigueur à la date du sinistre ;
2. version des conditions générales applicable à cette date ;
3. garantie souscrite (formule, option, extension pour le bien touché) ;
6. délai de déclaration (partie factuelle du contrôle 6) ;
7. montant : indemnité estimée = min(max(dommage − franchise, 0), plafond).

Les contrôles d'**interprétation** (4 : événement et bien garantis ;
5 : exclusions ; 6 : conditions de garantie) lisent les clauses retrouvées
par ``retrieval`` : une question fermée par contrôle au modèle de langage,
réponse vérifiée par l'application (``interpretation.py``). Sans modèle,
ils restent « à vérifier », avec les clauses à lire et leurs pages.

Le verdict découle des contrôles par une règle **non compensatoire** :
un contrôle bloquant suffit à écarter la garantie (rien ne rachète une
exclusion ou une garantie non souscrite) ; tous les contrôles satisfaits
donnent « potentiellement couvert » ; sinon « indéterminé », avec la liste
de ce qui manque.

Usage : ``python -m src.instruction S-01`` (sinistre de démonstration) ;
``--llm`` pour interroger le modèle de langage local (Ollama).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from src.database import applicable_version, connect
from src.interpretation import interpreter
from src.retrieval import retrieve

STATUTS = ("satisfait", "bloquant", "a_verifier", "sans_objet")
NOMS = {1: "Contrat en vigueur", 2: "Version applicable", 3: "Garantie souscrite",
        4: "Événement et bien garantis", 5: "Exclusions", 6: "Conditions et obligations",
        7: "Montant"}
# Nature du verdict quand un contrôle est bloquant.
NATURES = {1: "contrat non en vigueur", 2: "version inconnue", 3: "garantie non souscrite",
           4: "hors du champ de la garantie", 5: "exclusion", 6: "déchéance ou condition non remplie",
           7: "sous la franchise"}
BIENS = {"velo": "vélo", "mobilier_jardin": "mobilier de jardin"}
# Règle légale sur la déclaration tardive (voir docs/conception.md, contrôle 6).
REGLE_DELAI = {
    "LU": "Loi du 27 juillet 1997, art. 28 : réduction à concurrence du préjudice de l'assureur ; "
          "refus seulement en cas d'intention frauduleuse.",
    "BE": "Loi du 4 avril 2014, art. 76 : réduction à concurrence du préjudice de l'assureur ; "
          "refus seulement en cas d'intention frauduleuse.",
    "FR": "Code des assurances, art. L113-2 : déchéance opposable seulement si l'assureur prouve "
          "un préjudice ; jamais en cas de force majeure.",
    "CH": "LCA, art. 38 et 45 : réduction en cas de faute ; aucune sanction si la violation "
          "n'est pas imputable ou sans incidence.",
}


@dataclass
class Controle:
    numero: int
    nom: str
    statut: str                   # satisfait | bloquant | a_verifier | sans_objet
    constat: str                  # ce qui a été vérifié, en une phrase
    source: str                   # police, déclaration, catalogue, clause et page
    question: str | None = None   # question à poser si une information manque
    article_id: int | None = None
    page: int | None = None


@dataclass
class Instruction:
    sinistre: dict
    police: dict | None
    contrat: dict | None
    familles: list[str]
    controles: list[Controle] = field(default_factory=list)
    verdict: str = "indetermine"
    nature: str | None = None
    indemnite: float | None = None


# --- Outils ----------------------------------------------------------------

def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def jours_ouvres(debut: date, fin: date) -> int:
    """Jours ouvrés (lundi à vendredi) écoulés après ``debut`` jusqu'à ``fin``
    inclus. Les jours fériés ne sont pas déduits : le résultat peut
    surestimer le délai d'un ou deux jours (limite connue)."""
    jours, courant = 0, debut
    while courant < fin:
        courant += timedelta(days=1)
        if courant.weekday() < 5:
            jours += 1
    return jours


def euros(montant: float) -> str:
    """12500 → « 12 500 € »."""
    return f"{montant:,.0f} €".replace(",", "\u202f")


def indemnite(dommage: float, franchise: float, plafond: float) -> float:
    """Formule actuarielle simple : I = min(max(D − F, 0), P), avant vétusté."""
    return round(min(max(dommage - franchise, 0.0), plafond), 2)


def lire_sinistre(connection: sqlite3.Connection, sinistre_id: str) -> dict | None:
    row = connection.execute("SELECT * FROM sinistres WHERE id = ?", (sinistre_id,)).fetchone()
    return dict(row) if row else None


def lire_police(connection: sqlite3.Connection, numero: str) -> tuple[dict | None, set[str]]:
    row = connection.execute("SELECT * FROM polices WHERE numero = ?", (numero,)).fetchone()
    options = {r[0] for r in connection.execute(
        "SELECT option FROM police_options WHERE numero = ?", (numero,))}
    return (dict(row) if row else None), options


# --- Contrôles factuels ----------------------------------------------------

def controle_contrat(police: dict | None, survenance: date) -> Controle:
    """Contrôle 1 : la police était-elle en vigueur à la date du sinistre ?"""
    if police is None:
        return Controle(1, NOMS[1], "bloquant", "Police introuvable dans le portefeuille.", "Portefeuille")
    debut, fin = _date(police["date_effet"]), _date(police["date_fin"])
    source = f"Police {police['numero']}"
    if survenance < debut:
        return Controle(1, NOMS[1], "bloquant",
                        f"Sinistre du {survenance} antérieur à la prise d'effet ({debut}).", source)
    if fin is not None and survenance >= fin:
        return Controle(1, NOMS[1], "bloquant",
                        f"Contrat terminé le {fin}, avant le sinistre du {survenance}.", source)
    periode = f"depuis le {debut}" + (f" jusqu'au {fin}" if fin else "")
    return Controle(1, NOMS[1], "satisfait", f"Contrat en vigueur {periode}.", source)


def controle_version(connection: sqlite3.Connection, gamme: str,
                     survenance: date) -> tuple[Controle, dict | None]:
    """Contrôle 2 : quelles conditions générales s'appliquent à cette date ?"""
    row = applicable_version(connection, gamme, survenance.isoformat())
    if row is None:
        return (Controle(2, NOMS[2], "a_verifier",
                         f"Aucune version des conditions générales de {gamme} en base n'était en "
                         f"vigueur le {survenance}.", "Catalogue des contrats",
                         "Quelle version des conditions générales s'appliquait à la date du sinistre ?"),
                None)
    contrat = dict(row)
    return (Controle(2, NOMS[2], "satisfait",
                     f"{contrat['assureur']} — {contrat['produit']}, version {contrat['version']} "
                     f"(en vigueur depuis le {contrat['date_effet']}).",
                     f"Catalogue des contrats ({contrat['reference']})"), contrat)


def _acquise(garantie: dict, police: dict, options: set[str]) -> bool:
    if garantie["statut"] == "base":
        return True
    formules = set((garantie["formules"] or "").split("|")) - {""}
    return police["formule"] in formules or (garantie["option"] or "") in options


def _condition(garantie: dict) -> str:
    parts = []
    if garantie["formules"]:
        parts.append("formule " + " ou ".join(f.capitalize() for f in garantie["formules"].split("|")))
    if garantie["option"]:
        parts.append(f"option {garantie['option']}")
    return " ou ".join(parts) or "garantie de base"


def controle_garantie(connection: sqlite3.Connection, contrat: dict, police: dict,
                      options: set[str], familles: list[str],
                      bien: str | None) -> tuple[Controle, list[dict]]:
    """Contrôle 3 : la garantie concernée est-elle souscrite ? Une garantie
    est acquise si elle est de base, incluse dans la formule de la police,
    ou ajoutée par une option souscrite. Si le bien touché relève d'une
    extension (pack jardin...), cette extension doit aussi être souscrite."""
    connection.row_factory = sqlite3.Row
    catalogue = [dict(r) for r in connection.execute(
        "SELECT * FROM garanties WHERE contrat_id = ? ORDER BY id", (contrat["id"],))]
    concernees = [g for g in catalogue if g["famille"] in familles]
    if not concernees:
        return (Controle(3, NOMS[3], "a_verifier",
                         f"Aucune garantie « {', '.join(familles)} » dans le catalogue de ce contrat.",
                         "Catalogue des garanties",
                         "Quelle garantie des conditions particulières couvre cet événement ?"), [])
    acquises = [g for g in concernees if _acquise(g, police, options)]
    if not acquises:
        g = concernees[0]
        statut = "bloquant" if len(familles) == 1 else "a_verifier"
        question = None if statut == "bloquant" else (
            "Le classifieur hésite entre deux garanties : laquelle correspond au sinistre ?")
        return (Controle(3, NOMS[3], statut,
                         f"« {g['libelle']} » non souscrite : elle requiert {_condition(g)} "
                         f"(police : formule {police['formule']}, options "
                         f"{', '.join(sorted(options)) or 'aucune'}).",
                         f"Conditions générales p.{g['page']}", question, g["article_id"], g["page"]),
                [])
    retenues = acquises[:1]
    g = retenues[0]
    constat = f"« {g['libelle']} » acquise ({_condition(g)})."
    extensions = [e for e in catalogue if e["statut"] == "extension_bien" and bien
                  and bien in (e["biens"] or "").split("|")]
    for extension in extensions:
        if not _acquise(extension, police, options):
            return (Controle(3, NOMS[3], "bloquant",
                             f"{constat} Mais le bien « {BIENS.get(bien, bien)} » n'est couvert que par "
                             f"« {extension['libelle']} », non souscrit.",
                             f"Conditions générales p.{extension['page']}", None,
                             extension["article_id"], extension["page"]), [g])
        constat += f" Bien « {BIENS.get(bien, bien)} » couvert par « {extension['libelle']} »."
        retenues.append(extension)
    return (Controle(3, NOMS[3], "satisfait", constat, f"Conditions générales p.{g['page']}",
                     None, g["article_id"], g["page"]), retenues)


def controle_delai(contrat: dict, familles: list[str], sinistre: dict) -> Controle:
    """Contrôle 6, partie factuelle : la déclaration respecte-t-elle le délai
    du contrat ? Le délai court à partir de la connaissance du sinistre.
    Un retard n'est jamais bloquant à lui seul (voir REGLE_DELAI)."""
    connaissance = _date(sinistre["date_connaissance"] or sinistre["date_survenance"])
    declaration = _date(sinistre["date_declaration"])
    source = f"Conditions générales p.{contrat['page_delais']}" if contrat["page_delais"] else "Contrat"
    if declaration is None:
        return Controle(6, "Délai de déclaration", "a_verifier", "Date de déclaration inconnue.",
                        "Déclaration", "À quelle date le sinistre a-t-il été déclaré ?")
    limite = contrat["delai_vol"] if "vol" in familles else contrat["delai_declaration"]
    if limite is None:
        return Controle(6, "Délai de déclaration", "a_verifier", "Délai contractuel non renseigné.",
                        source, "Quel est le délai de déclaration prévu au contrat ?")
    ouvres = contrat["unite_delai"] == "jours_ouvres"
    ecoules = jours_ouvres(connaissance, declaration) if ouvres else (declaration - connaissance).days
    def duree(n: int) -> str:
        mot = "jour ouvré" if ouvres else "jour"
        return f"{n} {mot}" if n <= 1 else f"{n} {mot.replace('jour', 'jours').replace('ouvré', 'ouvrés')}"
    constat = (f"Déclaré {duree(ecoules)} après la connaissance du sinistre ({connaissance}) ; "
               f"délai du contrat : {duree(limite)}.")
    if ecoules <= limite:
        return Controle(6, "Délai de déclaration", "satisfait", constat, source)
    regle = REGLE_DELAI.get(contrat["pays"], "")
    return Controle(6, "Délai de déclaration", "a_verifier", f"{constat} Retard. {regle}", source,
                    "Le retard a-t-il causé un préjudice à l'assureur ? Une raison l'explique-t-elle ?")


def controle_montant(police: dict, retenues: list[dict], montant: float | None) -> tuple[Controle, float | None]:
    """Contrôle 7 : indemnité estimée, avant vétusté."""
    if montant is None:
        return (Controle(7, NOMS[7], "a_verifier", "Montant du dommage non chiffré.", "Déclaration",
                         "Quel est le montant du dommage (facture, devis) ?"), None)
    plafonds = [police["plafond_contenu"]] + [g["plafond"] for g in retenues if g.get("plafond")]
    plafond, franchise = min(plafonds), police["franchise"]
    montant_du = indemnite(montant, franchise, plafond)
    constat = (f"Indemnité estimée {euros(montant_du)} = min(max({euros(montant)} − "
               f"{euros(franchise)}, 0), {euros(plafond)}), avant vétusté.")
    statut = "satisfait" if montant_du > 0 else "bloquant"
    return Controle(7, NOMS[7], statut, constat, f"Police {police['numero']} (franchise, plafond)"), montant_du


def faits(sinistre: dict) -> str:
    """Faits connus de la déclaration, transmis avec chaque question fermée."""
    parties = [f"bien touché : {BIENS.get(sinistre['bien'], sinistre['bien'] or 'non précisé')}",
               f"survenu le {sinistre['date_survenance']}"]
    if sinistre["date_connaissance"] and sinistre["date_connaissance"] != sinistre["date_survenance"]:
        parties.append(f"constaté le {sinistre['date_connaissance']}")
    if sinistre["montant_estime"] is not None:
        parties.append(f"montant estimé {euros(sinistre['montant_estime'])}")
    return " ; ".join(parties)


def controles_interpretation(connection: sqlite3.Connection, contrat: dict, sinistre: dict,
                             familles: list[str], llm: Callable | None) -> list[Controle]:
    """Contrôles 4, 5 et 6 (conditions) : clauses retrouvées dans le contrat
    applicable, puis une question fermée par contrôle."""
    clauses = retrieve(connection, contrat["code"], sinistre["description"], familles)
    return [interpreter(numero, sinistre["description"], faits(sinistre), clauses, familles, llm)
            for numero in (4, 5, 6)]


# --- Verdict -----------------------------------------------------------------

def verdict(controles: list[Controle]) -> tuple[str, str | None]:
    """Agrégation non compensatoire : un contrôle bloquant écarte la garantie,
    quel que soit le résultat des autres ; tous satisfaits (ou sans objet)
    donnent « potentiellement couvert » ; sinon « indéterminé »."""
    bloquants = [c for c in controles if c.statut == "bloquant"]
    if bloquants:
        return "potentiellement_exclu", NATURES[bloquants[0].numero]
    if all(c.statut in ("satisfait", "sans_objet") for c in controles):
        return "potentiellement_couvert", None
    return "indetermine", None


def instruire(connection: sqlite3.Connection, sinistre_id: str, familles: list[str],
              llm: Callable | None = None) -> Instruction:
    """Instruction complète d'un sinistre enregistré : contrôles factuels,
    contrôles d'interprétation (avec le modèle ``llm`` s'il est fourni),
    puis verdict."""
    connection.row_factory = sqlite3.Row
    sinistre = lire_sinistre(connection, sinistre_id)
    if sinistre is None:
        raise KeyError(f"sinistre inconnu : {sinistre_id}")
    survenance = _date(sinistre["date_survenance"])
    police, options = lire_police(connection, sinistre["numero_police"])
    instruction = Instruction(sinistre, police, None, familles)
    controles = [controle_contrat(police, survenance)]
    if police is not None:
        c2, contrat = controle_version(connection, police["gamme"], survenance)
        controles.append(c2)
        instruction.contrat = contrat
        if contrat is not None:
            c3, retenues = controle_garantie(connection, contrat, police, options, familles,
                                             sinistre["bien"])
            controles.append(c3)
            controles += controles_interpretation(connection, contrat, sinistre, familles, llm)
            controles.append(controle_delai(contrat, familles, sinistre))
            c7, instruction.indemnite = controle_montant(police, retenues, sinistre["montant_estime"])
            controles.append(c7)
    instruction.controles = sorted(controles, key=lambda c: c.numero)
    instruction.verdict, instruction.nature = verdict(instruction.controles)
    return instruction


def enregistrer(connection: sqlite3.Connection, instruction: Instruction,
                probabilites: dict | None = None, modele: str | None = None) -> int:
    """Trace l'instruction dans les tables ``analyses`` et ``controles``."""
    cursor = connection.execute(
        "INSERT INTO analyses (sinistre_id, contrat_id, familles, verdict, nature, indemnite_estimee,"
        " modele) VALUES (?,?,?,?,?,?,?)",
        (instruction.sinistre["id"], instruction.contrat["id"] if instruction.contrat else None,
         json.dumps(probabilites or {f: None for f in instruction.familles}), instruction.verdict,
         instruction.nature, instruction.indemnite, modele))
    analyse_id = cursor.lastrowid
    connection.executemany(
        "INSERT INTO controles (analyse_id, numero, nom, statut, constat, source, article_id, question)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [(analyse_id, c.numero, c.nom, c.statut, c.constat, c.source, c.article_id, c.question)
         for c in instruction.controles])
    connection.commit()
    return analyse_id


def afficher(instruction: Instruction) -> str:
    """Fiche d'instruction lisible dans un terminal."""
    s = instruction.sinistre
    lignes = [f"Sinistre {s['id']} — police {s['numero_police']} — survenu le {s['date_survenance']}",
              f"« {s['description']} »",
              f"Garantie(s) examinée(s) : {', '.join(instruction.familles)}", ""]
    symboles = {"satisfait": "OK ", "bloquant": "NON", "a_verifier": " ? ", "sans_objet": " - "}
    for c in instruction.controles:
        lignes.append(f"[{symboles[c.statut]}] {c.numero}. {c.nom} — {c.constat}  ({c.source})")
        if c.question:
            lignes.append(f"        Question : {c.question}")
    nature = f" ({instruction.nature})" if instruction.nature else ""
    lignes += ["", f"Verdict : {instruction.verdict}{nature}",
               "Aide à la décision : la décision appartient au gestionnaire."]
    return "\n".join(lignes)


if __name__ == "__main__":
    from src.classifier import load_model, predict
    from src.decision import call_ollama

    arguments = [a for a in sys.argv[1:] if not a.startswith("--")]
    llm = call_ollama if "--llm" in sys.argv else None
    connection = connect()
    model = load_model()
    identifiants = arguments or [r[0] for r in connection.execute("SELECT id FROM sinistres ORDER BY id")]
    for identifiant in identifiants:
        sinistre = lire_sinistre(connection, identifiant)
        familles = predict(model, sinistre["description"]).families
        print(afficher(instruire(connection, identifiant, familles, llm)), "\n")
