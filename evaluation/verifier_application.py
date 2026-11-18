"""Vérifie une application en marche (locale ou distante) par son API HTTP.

Attend que ``/ready`` réponde « ready », puis instruit les sinistres de
démonstration et affiche, pour chacun, le verdict et le statut des 7
contrôles. Bibliothèque standard uniquement.

Usage :
    python evaluation/verifier_application.py --url http://localhost:7860
    python evaluation/verifier_application.py --url https://….hf.space --sinistres S-01 S-08
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


def get(url: str, timeout: float = 30):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def post(url: str, body: dict, timeout: float = 900):
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def wait_until_ready(base: str, minutes: float) -> dict:
    deadline = time.time() + minutes * 60
    while True:
        try:
            status, body = get(f"{base}/ready")
            if status == 200 and body.get("status") == "ready":
                return body
            print("pas encore prêt :", body.get("checks"))
        except Exception as error:   # serveur pas encore démarré
            print("pas de réponse :", type(error).__name__)
        if time.time() > deadline:
            raise SystemExit("L'application n'est pas prête dans le délai.")
        time.sleep(20)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:7860")
    parser.add_argument("--attente-minutes", type=float, default=30)
    parser.add_argument("--sinistres", nargs="*", default=["S-01", "S-04", "S-06", "S-08"])
    args = parser.parse_args()
    base = args.url.rstrip("/")
    print("Prête :", json.dumps(wait_until_ready(base, args.attente_minutes), ensure_ascii=False))
    ok = 0
    for identifiant in args.sinistres:
        start = time.time()
        result = post(f"{base}/api/instruire", {"sinistre_id": identifiant})
        etats = " ".join(f"{c['numero']}:{c['statut']}" for c in result["controles"])
        print(f"{identifiant} ({time.time() - start:.0f} s) verdict={result['verdict']} "
              f"nature={result['nature']} | {etats}")
        ok += len(result["controles"]) >= 7
    print(f"BILAN : {ok}/{len(args.sinistres)} instructions complètes (7 contrôles)")
    if ok != len(args.sinistres):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
