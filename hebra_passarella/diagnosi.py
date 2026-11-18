"""Diagnosi de la passarel·la amb el lector real (primera prova amb un R700).

  python3 -m hebra_passarella.diagnosi /etc/hebra/passarella.toml --segons 30

Fa, en ordre, i diu clarament què falla:
  1. Plataforma: respon /salut i accepta la clau de la passarel·la (lot buit).
  2. Lector: estat (`GET /api/v1/status`), preset i inici amb els camins de passarella.toml.
  3. Flux: escolta `--segons` segons, compta lectures per antena i etiqueta (RSSI mitjà),
     i desa les línies crues a un fitxer .jsonl per poder revisar el format exacte.
  4. Atura el lector.

No envia cap lectura a la plataforma: és només per comprovar-ho tot abans d'engegar el servei.
Vegeu docs/PROVA-R700.md.
"""

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .__main__ import carrega
from .lector import ClientLector, ConfigLector, interpreta


def _config_lector(cfg: dict) -> ConfigLector:
    l = cfg["lector"]
    return ConfigLector(
        url=l["url"], usuari=l.get("usuari", "root"), contrasenya=l.get("contrasenya", "impinj"),
        verifica_tls=l.get("verifica_tls", False), ports=tuple(l.get("ports", [1, 2, 3])),
        potencia_cdbm=l.get("potencia_cdbm", 1500),
        **{k: l[k] for k in ("cami_preset", "cami_inici", "cami_aturada", "cami_flux") if k in l})


def _error_http(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        cos = e.read()[:300].decode("utf-8", "replace")
        return f"HTTP {e.code} {e.reason} {cos}".strip()
    return f"{type(e).__name__}: {e}"


class Informe:
    def __init__(self):
        self.errors = 0

    def ok(self, text: str) -> None:
        print(f"  OK     {text}")

    def avis(self, text: str) -> None:
        print(f"  AVÍS   {text}")

    def error(self, text: str) -> None:
        self.errors += 1
        print(f"  ERROR  {text}")


def comprova_plataforma(cfg: dict, inf: Informe) -> None:
    print("1. Plataforma")
    p = cfg.get("plataforma", {})
    url = p.get("url", "").rstrip("/")
    if not url:
        inf.avis("[plataforma] url buida: no es comprova")
        return
    try:
        with urllib.request.urlopen(f"{url}/salut", timeout=10) as r:
            inf.ok(f"{url}/salut respon: {r.read(200).decode()}")
    except Exception as e:
        inf.error(f"{url}/salut no respon ({_error_http(e)}). Mireu la xarxa de la botiga i el domini.")
        return
    req = urllib.request.Request(f"{url}/api/v1/lots", method="POST",
                                 data=json.dumps({"lectures": [], "sensors": []}).encode(),
                                 headers={"Content-Type": "application/json", "X-Hebra-Clau": p.get("clau", "")})
    try:
        with urllib.request.urlopen(req, timeout=10):
            inf.ok("la clau de la passarel·la és correcta")
    except Exception as e:
        inf.error(f"la plataforma no accepta la clau ({_error_http(e)}): ha de ser HEBRA_CLAU_PASSARELLA del servidor")


def comprova_lector(cfg: dict, segons: float, sortida: Path, inf: Informe) -> dict:
    print("2. Lector")
    lc = _config_lector(cfg)
    client = ClientLector(lc)
    res: dict = {"linies": 0, "lectures": 0, "no_json": 0, "altres": defaultdict(int),
                 "per_etiqueta": defaultdict(list), "desfasament_s": []}
    try:
        with client._crida("GET", "/api/v1/status") as r:
            inf.ok(f"estat del lector: {r.read(300).decode('utf-8', 'replace')}")
    except Exception as e:
        inf.avis(f"GET /api/v1/status: {_error_http(e)} (la resta pot funcionar igualment)")
    try:
        client.prepara_i_engega()
        inf.ok(f"preset desat i inventari engegat (ports {list(lc.ports)}, {lc.potencia_cdbm / 100:.1f} dBm)")
    except Exception as e:
        inf.error(f"no s'ha pogut desar el preset o engegar ({_error_http(e)}). "
                  f"Comproveu al Swagger del lector cami_preset={lc.cami_preset} i cami_inici={lc.cami_inici}, "
                  "i l'usuari i la contrasenya.")
        return res

    print(f"3. Flux ({lc.cami_flux}) durant {segons:.0f} s: acosteu etiquetes a cada antena")
    resposta: list = []

    def llegeix() -> None:
        try:
            with client._crida("GET", lc.cami_flux, timeout=segons + 30) as r, sortida.open("w", encoding="utf-8") as fo:
                resposta.append(r)
                for brut in r:
                    linia = brut.decode("utf-8", "replace").strip()
                    if not linia:
                        continue
                    fo.write(linia + "\n")
                    res["linies"] += 1
                    try:
                        ev = json.loads(linia)
                    except json.JSONDecodeError:
                        res["no_json"] += 1
                        continue
                    lectura = interpreta(linia)
                    if lectura:
                        res["lectures"] += 1
                        res["per_etiqueta"][(lectura.port, lectura.epc_hex)].append(lectura.rssi_dbm)
                        if "timestamp" in ev:
                            res["desfasament_s"].append((lectura.ts - datetime.now(timezone.utc)).total_seconds())
                    else:
                        res["altres"][next(iter(ev), "?") if isinstance(ev, dict) else "?"] += 1
        except Exception as e:
            if not res.get("aturat"):
                res["error_flux"] = _error_http(e)

    fil = threading.Thread(target=llegeix, daemon=True)
    fil.start()
    fil.join(segons)
    res["aturat"] = True
    print("4. Aturada")
    try:
        client._crida("POST", lc.cami_aturada).close()
        inf.ok("lector aturat")
    except Exception as e:
        inf.avis(f"no s'ha pogut aturar ({_error_http(e)}): comproveu cami_aturada={lc.cami_aturada}")
    for r in resposta:
        try:
            r.close()
        except Exception:
            pass
    fil.join(5)
    return res


def resumeix(res: dict, sortida: Path, inf: Informe) -> None:
    print("Resultat")
    if res.get("error_flux"):
        inf.error(f"el flux ha fallat: {res['error_flux']}. Comproveu cami_flux al Swagger del lector.")
    if not res["linies"]:
        if not res.get("error_flux"):
            inf.error("el flux no ha enviat res: no hi havia etiquetes a prop o el camí del flux no és aquest")
        return
    inf.ok(f"{res['linies']} línies rebudes, {res['lectures']} lectures d'etiqueta (crues a {sortida})")
    if res["no_json"]:
        inf.error(f"{res['no_json']} línies no són JSON: el flux no té el format esperat (envieu {sortida.name})")
    if res["altres"]:
        inf.ok("altres esdeveniments: " + ", ".join(f"{k} ×{v}" for k, v in res["altres"].items()))
    if res["linies"] and not res["lectures"]:
        inf.error(f"cap línia s'ha entès com a lectura (TagInventoryEvent): envieu {sortida.name} a qui mantingui el codi")
    if res["desfasament_s"]:
        d = statistics.median(res["desfasament_s"])
        (inf.avis if abs(d) > 30 else inf.ok)(f"rellotge del lector respecte a la passarel·la: {d:+.1f} s")
    if res["per_etiqueta"]:
        print("\n  antena  etiqueta (EPC)              lectures  RSSI mitjà  mín / màx (dBm)")
        for (port, epc), rssi in sorted(res["per_etiqueta"].items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
            print(f"  {port:>6}  {epc:<26}  {len(rssi):>8}  {statistics.mean(rssi):>10.1f}  "
                  f"{min(rssi):.1f} / {max(rssi):.1f}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Diagnosi de la passarel·la i del lector R700")
    ap.add_argument("config", help="fitxer passarella.toml")
    ap.add_argument("--segons", type=float, default=30, help="segons escoltant el flux (30)")
    ap.add_argument("--sortida", help="fitxer per a les línies crues (per defecte diagnosi-<hora>.jsonl)")
    ap.add_argument("--sense-plataforma", action="store_true", help="no comprovis el servidor")
    args = ap.parse_args(argv)
    cfg = carrega(args.config)
    sortida = Path(args.sortida or f"diagnosi-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl")
    inf = Informe()
    if not args.sense_plataforma:
        comprova_plataforma(cfg, inf)
    t0 = time.monotonic()
    res = comprova_lector(cfg, args.segons, sortida, inf)
    resumeix(res, sortida, inf)
    print(f"\n{'Tot correcte' if not inf.errors else f'{inf.errors} errors'} ({time.monotonic() - t0:.0f} s)")
    return 1 if inf.errors else 0


if __name__ == "__main__":
    sys.exit(main())
