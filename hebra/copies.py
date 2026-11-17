"""Còpies de seguretat de la base de dades (SQLite).

Tota la plataforma és un sol fitxer SQLite. Aquest mòdul en fa una còpia
coherent mentre la web funciona (API de còpia en calent de SQLite, compatible
amb WAL), la comprova (`PRAGMA integrity_check`), la comprimeix i en guarda
un nombre limitat a la carpeta local. Si hi ha un destí remot configurat,
l'envia fora del servidor amb `rclone` (qualsevol emmagatzematge compatible:
Oracle Object Storage, Cloudflare R2, Backblaze B2, Google Drive...).

  python -m hebra.admin copia                 # fa la còpia (el temporitzador systemd ho fa cada nit)
  python -m hebra.admin copies                # llista les còpies locals
  python -m hebra.admin restaura FITXER.db.gz # restaura (amb el servei aturat)

Variables d'entorn (vegeu .env.example):
  HEBRA_COPIES_CARPETA   carpeta local (per defecte, «copies» al costat de la BD)
  HEBRA_COPIES_DIARIES   quantes còpies recents es guarden (14)
  HEBRA_COPIES_SETMANALS quantes còpies de diumenge es guarden a més (8)
  HEBRA_COPIES_DESTI     destí d'rclone, p. ex. «copies:hebra-copies» (buit = només local)
  HEBRA_COPIES_REMOT_DIES dies que es guarden al destí remot (60; 0 = no s'esborra res)

Les còpies contenen correus i resums de contrasenya dels usuaris del tauler:
el destí remot ha de ser privat i, millor, xifrat (remot «crypt» d'rclone).
"""

import gzip
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("hebra.copies")

PREFIX = "hebra-"
SUFIX = ".db.gz"
CLAU_ESTAT = "copia_seguretat"
HORES_ALERTA = 36  # més d'un dia i mig sense còpia: alguna cosa falla


def _int(nom: str, defecte: int) -> int:
    return int(os.environ.get(nom, defecte))


@dataclass(frozen=True)
class ConfigCopies:
    carpeta: str = field(default_factory=lambda: os.environ.get("HEBRA_COPIES_CARPETA", ""))
    diaries: int = field(default_factory=lambda: _int("HEBRA_COPIES_DIARIES", 14))
    setmanals: int = field(default_factory=lambda: _int("HEBRA_COPIES_SETMANALS", 8))
    desti: str = field(default_factory=lambda: os.environ.get("HEBRA_COPIES_DESTI", ""))
    remot_dies: int = field(default_factory=lambda: _int("HEBRA_COPIES_REMOT_DIES", 60))

    def carpeta_per(self, ruta_bd: str) -> Path:
        if self.carpeta:
            return Path(self.carpeta)
        return Path(ruta_bd).resolve().parent / "copies"


class ErrorCopia(RuntimeError):
    pass


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _comprova(ruta: Path) -> None:
    """Falla si el fitxer no és una base de dades SQLite sencera."""
    try:
        c = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        try:
            res = c.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            c.close()
    except sqlite3.DatabaseError as e:
        raise ErrorCopia(f"La còpia no és una base de dades vàlida: {e}") from e
    if res != "ok":
        raise ErrorCopia(f"La còpia no passa la comprovació d'integritat: {res}")


def _nom(ara: datetime) -> str:
    return f"{PREFIX}{ara.strftime('%Y-%m-%dT%H%M%SZ')}{SUFIX}"


def _data_del_nom(p: Path) -> datetime | None:
    try:
        return datetime.strptime(p.name[len(PREFIX):-len(SUFIX)], "%Y-%m-%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def llista(carpeta: Path) -> list[Path]:
    """Còpies de la carpeta, de la més nova a la més antiga."""
    if not carpeta.is_dir():
        return []
    cs = [p for p in carpeta.glob(f"{PREFIX}*{SUFIX}") if _data_del_nom(p)]
    return sorted(cs, key=lambda p: _data_del_nom(p), reverse=True)


def rota(carpeta: Path, diaries: int, setmanals: int) -> list[Path]:
    """Guarda les `diaries` més noves (una per dia) i una per setmana de les `setmanals` setmanes
    anteriors; esborra la resta. Retorna les esborrades."""
    guarda: set[Path] = set()
    dies: set = set()
    setmanes: set = set()
    for p in llista(carpeta):
        d = _data_del_nom(p)
        if len(dies) < diaries and d.date() not in dies:
            dies.add(d.date())
            guarda.add(p)
            continue
        setmana = d.isocalendar()[:2]
        if len(setmanes) < setmanals and setmana not in setmanes and d.date() not in dies:
            setmanes.add(setmana)
            guarda.add(p)
    esborrades = []
    for p in llista(carpeta):
        if p not in guarda:
            p.unlink(missing_ok=True)
            Path(str(p) + ".sha256").unlink(missing_ok=True)
            esborrades.append(p)
    return esborrades


def _rclone(*args: str) -> None:
    if not shutil.which("rclone"):
        raise ErrorCopia("No trobo rclone: instal·leu-lo (sudo apt install rclone) o deixeu buit HEBRA_COPIES_DESTI")
    r = subprocess.run(["rclone", *args], capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise ErrorCopia(f"rclone {args[0]} ha fallat: {r.stderr.strip()[-500:]}")


def _desa_estat(con: sqlite3.Connection, estat: dict) -> None:
    con.execute("""INSERT INTO parametre (botiga_id, clau, valor) VALUES ('*', ?, ?)
                   ON CONFLICT(botiga_id, clau) DO UPDATE SET valor = excluded.valor""",
                (CLAU_ESTAT, json.dumps(estat, ensure_ascii=False)))
    con.commit()


def fes_copia(ruta_bd: str, cc: ConfigCopies | None = None, ara: datetime | None = None) -> dict:
    """Fa una còpia comprovada i comprimida, rota les antigues i, si cal, l'envia fora.

    Deixa el resultat (també si falla l'enviament remot) a `parametre` perquè
    l'estat del sistema el mostri. Llança `ErrorCopia` si la còpia local falla.
    """
    cc = cc or ConfigCopies()
    ara = ara or datetime.now(timezone.utc)
    if not Path(ruta_bd).is_file():
        raise ErrorCopia(f"No trobo la base de dades: {ruta_bd}")
    carpeta = cc.carpeta_per(ruta_bd)
    carpeta.mkdir(parents=True, exist_ok=True)
    os.chmod(carpeta, 0o700)
    desti = carpeta / _nom(ara)

    with tempfile.TemporaryDirectory(dir=carpeta) as tmp:
        cru = Path(tmp) / "copia.db"
        origen = sqlite3.connect(ruta_bd, timeout=60)
        try:
            dest = sqlite3.connect(cru)
            try:
                origen.backup(dest)  # còpia en calent: coherent encara que la web escrigui
            finally:
                dest.close()
        finally:
            origen.close()
        _comprova(cru)
        mida_bd = cru.stat().st_size
        parcial = Path(tmp) / desti.name
        with cru.open("rb") as fi, gzip.open(parcial, "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo, 1 << 20)
        os.chmod(parcial, 0o600)
        os.replace(parcial, desti)  # només apareix quan és sencera
    suma = _sha256(desti)
    Path(str(desti) + ".sha256").write_text(f"{suma}  {desti.name}\n", encoding="utf-8")
    esborrades = rota(carpeta, cc.diaries, cc.setmanals)

    estat = {"darrera": ara.isoformat(timespec="seconds"), "fitxer": desti.name,
             "mida_bd": mida_bd, "mida_copia": desti.stat().st_size, "sha256": suma,
             "locals": len(llista(carpeta)), "remot": None, "error_remot": None}
    if cc.desti:
        try:
            _rclone("copyto", str(desti), f"{cc.desti.rstrip('/')}/{desti.name}")
            if cc.remot_dies > 0:
                _rclone("delete", "--min-age", f"{cc.remot_dies}d", "--include", f"{PREFIX}*{SUFIX}", cc.desti)
            estat["remot"] = cc.desti
        except (ErrorCopia, subprocess.TimeoutExpired) as e:
            estat["error_remot"] = str(e)
            log.error("Còpia local feta, però no s'ha pogut enviar fora: %s", e)

    con = sqlite3.connect(ruta_bd, timeout=60)
    try:
        _desa_estat(con, estat)
    finally:
        con.close()
    log.info("Còpia %s (%d B), %d antigues esborrades", desti.name, estat["mida_copia"], len(esborrades))
    return estat


def restaura(copia: str, ruta_bd: str) -> Path | None:
    """Substitueix la base de dades per una còpia (`.db.gz` o `.db`). Atureu abans el servei web.

    La base de dades actual es guarda al costat amb el sufix `.abans-de-restaurar-<hora>`.
    Retorna aquest fitxer (o None si no n'hi havia).
    """
    src = Path(copia)
    if not src.is_file():
        raise ErrorCopia(f"No trobo la còpia: {copia}")
    suma = Path(str(src) + ".sha256")
    if suma.is_file() and suma.read_text(encoding="utf-8").split()[0] != _sha256(src):
        raise ErrorCopia("La suma SHA-256 no coincideix: la còpia està malmesa")
    bd = Path(ruta_bd)
    bd.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=bd.parent) as tmp:
        nova = Path(tmp) / "restaurada.db"
        if src.name.endswith(".gz"):
            with gzip.open(src, "rb") as fi, nova.open("wb") as fo:
                shutil.copyfileobj(fi, fo, 1 << 20)
        else:
            shutil.copyfile(src, nova)
        _comprova(nova)
        anterior = None
        if bd.exists():
            anterior = bd.with_name(f"{bd.name}.abans-de-restaurar-{datetime.now().strftime('%Y%m%dT%H%M%S')}")
            os.replace(bd, anterior)
        for extra in ("-wal", "-shm"):  # pertanyen a la base de dades antiga
            Path(str(bd) + extra).unlink(missing_ok=True)
        os.replace(nova, bd)
    return anterior


def estat(con: sqlite3.Connection, ara: datetime | None = None) -> dict:
    """Per a l'estat del sistema: quan es va fer la darrera còpia i si va arribar fora."""
    fila = con.execute("SELECT valor FROM parametre WHERE botiga_id = '*' AND clau = ?", (CLAU_ESTAT,)).fetchone()
    if not fila:
        return {"darrera": None, "hores": None, "remot": None, "error_remot": None, "alerta": True,
                "hores_alerta": HORES_ALERTA}
    e = json.loads(fila[0])
    ara = ara or datetime.now(timezone.utc)
    hores = round((ara - datetime.fromisoformat(e["darrera"])).total_seconds() / 3600, 1)
    return {"darrera": e["darrera"], "hores": hores, "remot": e.get("remot"), "error_remot": e.get("error_remot"),
            "alerta": hores > HORES_ALERTA or bool(e.get("error_remot")), "hores_alerta": HORES_ALERTA}


__all__ = ["ConfigCopies", "ErrorCopia", "fes_copia", "restaura", "llista", "rota", "estat"]
