# ---------------------------------------------------------------------------
# Projet  : Claim Coverage Checker (instruction d'un sinistre habitation)
# Fichier : src/portefeuille.py
# Auteur  : Thierry MBARGA
# Rôle    : générer un grand portefeuille de polices fictives pour tester
#           l'instruction à l'échelle (100 000 polices par défaut).
# Entrée  : nombre de polices.  Sortie : polices et options ajoutées à la base.
# ---------------------------------------------------------------------------
"""Portefeuille synthétique de polices, pour tester l'instruction à l'échelle.

Les polices sont générées de façon reproductible (graine fixe) et marquées
``origine = 'synthetique'`` : elles ne se mélangent pas aux polices de
démonstration. Répartition :

- trois produits, à parts égales ;
- formule : Sogessur Initiale 40 %, Confort 40 %, Optimale 20 % ;
- options : vol 50 % (Baloise, Ethias) ou 30 % (Sogessur Initiale), pack
  jardin 25 % (Baloise, Sogessur) ;
- prise d'effet uniforme de 2015 à 2026 ; 10 % de contrats résiliés ;
- plafond du contenu de 15 000 à 150 000 euros ; franchise parmi
  0, 150, 250, 300 et 500 euros.

Usage : ``python -m src.portefeuille 100000`` (ajoute 100 000 polices à la base).
"""
from __future__ import annotations

import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

from src.database import DB_PATH

# Graine fixe : le même portefeuille à chaque génération.
# Pour chaque produit : pays, formules (avec leur part) et probabilité de chaque option.
SEED = 2026
GAMMES = {
    "baloise_lu_home": {"pays": "LU", "formules": [("HOME", 1.0)], "options": {"VOL": 0.5, "PACK_JARDIN": 0.25}},
    "ethias_be_habitation": {"pays": "BE", "formules": [("HABITATION", 1.0)], "options": {"VOL": 0.5}},
    "sogessur_fr_habitation": {"pays": "FR", "formules": [("INITIALE", 0.4), ("CONFORT", 0.4), ("OPTIMALE", 0.2)],
                               "options": {"VOL": 0.3, "PACK_JARDIN": 0.25}},
}
FRANCHISES = [0, 150, 250, 300, 500]
DEBUT, FIN = date(2015, 1, 1), date(2026, 10, 1)


def generer(n: int, seed: int = SEED) -> tuple[list[tuple], list[tuple]]:
    """n polices et leurs options, sous forme de lignes prêtes à insérer."""
    rng = random.Random(seed)
    polices, options = [], []
    gammes = list(GAMMES)
    jours = (FIN - DEBUT).days
    for i in range(1, n + 1):
        # Les 3 produits à tour de rôle : parts égales.
        gamme = gammes[i % 3]
        regles = GAMMES[gamme]
        noms, poids = zip(*regles["formules"])
        # Tirage de la formule selon les poids (ex. 40 % / 40 % / 20 %).
        formule = rng.choices(noms, poids)[0]
        effet = DEBUT + timedelta(days=rng.randrange(jours))
        fin = None
        # 10 % de contrats résiliés, entre 1 et 8 ans après la prise d'effet.
        if rng.random() < 0.10:
            fin = min(effet + timedelta(days=rng.randint(365, 8 * 365)), FIN)
        numero = f"{regles['pays']}-{i:07d}"
        polices.append((numero, gamme, formule, effet.isoformat(), fin.isoformat() if fin else None,
                        # Plafond du contenu : multiple de 1 000 € entre 15 000 et 150 000 €.
                        float(rng.randrange(15, 151) * 1000), float(rng.choice(FRANCHISES)), "synthetique"))
        for option, probabilite in regles["options"].items():
            if option == "VOL" and formule in ("CONFORT", "OPTIMALE"):
                continue      # vol déjà inclus dans ces formules
            if rng.random() < probabilite:
                options.append((numero, option))
    return polices, options


def ajouter(n: int, db_path: Path = DB_PATH) -> tuple[int, int]:
    """Remplace le portefeuille synthétique de la base par n nouvelles polices."""
    polices, options = generer(n)
    connection = sqlite3.connect(db_path)
    try:
        # Seul le portefeuille synthétique est remplacé ; les polices de démonstration restent.
        connection.execute("DELETE FROM police_options WHERE numero IN "
                           "(SELECT numero FROM polices WHERE origine = 'synthetique')")
        connection.execute("DELETE FROM polices WHERE origine = 'synthetique'")
        connection.executemany("INSERT INTO polices VALUES (?,?,?,?,?,?,?,?)", polices)
        connection.executemany("INSERT INTO police_options VALUES (?,?)", options)
        connection.commit()
    finally:
        connection.close()
    return len(polices), len(options)


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    n_polices, n_options = ajouter(count)
    print(f"{n_polices} polices synthétiques et {n_options} options ajoutées à {DB_PATH}")
