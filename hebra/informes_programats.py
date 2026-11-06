"""Informes programats i lliurats (docs/ESPECIFICACIO-v3.md, E.1, E.3 i E.4).

Programació (`programacio_informe`), en hora local de la botiga (`botiga.zona_horaria`;
Europe/Madrid si l'informe és de totes les botigues):
  * `diari`:    cada dia a `hora`; informe del dia anterior.
  * `setmanal`: el `dia_setmana` (0 = dilluns) a `hora`; setmana anterior completa (dilluns-diumenge).
  * `mensual`:  el `dia_mes` (1-28) a `hora`; mes anterior.
  * `temporada`, `pilot`, `mango`: una vegada, a `data` + `hora`. Període:
      temporada → els 182 dies anteriors (mitja temporada llarga, unes 26 setmanes);
      pilot i mango → de l'inici del pilot (taula `pilot`) fins al dia abans, o els 42 dies anteriors.

«Toca?» (`toca`, funció pura): la darrera ocurrència programada que ja ha passat,
si és posterior a la data de creació i a la darrera execució. Si el servidor ha estat
aturat, en tornar només genera l'ocurrència més recent (no recupera tots els buits).
Les hores es construeixen en hora local (a les 08:00 ho és tant a l'hivern com a
l'estiu) i es comparen sempre en UTC. Una hora que no existeix el dia del canvi
d'hora (02:30 a finals de març) es desplaça endavant; una que existeix dues vegades
(finals d'octubre) es fa la primera vegada.

Lliurament: `genera` desa la instantània JSON a `informe_lliurat`; `envia_lliurat`
n'envia el PDF per correu a l'equip de la marca (mai a clients finals).
"""

import json
import logging
import sqlite3
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from . import analitica, correu, informe_pdf, temps
from .config import Config

log = logging.getLogger("hebra.informes")

TIPUS = ("diari", "setmanal", "mensual", "temporada", "pilot", "mango")
UNA_VEGADA = ("temporada", "pilot", "mango")
DIES_TEMPORADA = 182
DIES_PILOT = 42
CAMPS = ("id", "botiga_id", "tipus", "actiu", "dia_setmana", "dia_mes", "data", "hora", "destinataris")


# ---------------------------------------------------------------- Calendari (funcions pures)


def _local(d: date, hora: str, zona: ZoneInfo) -> datetime:
    """Hora local real d'una data i una hora «HH:MM» (gestiona els canvis d'hora)."""
    h, m = (int(x) for x in hora.split(":"))
    ingenua = datetime.combine(d, time(h, m))
    dt = ingenua.replace(tzinfo=zona, fold=0)
    # Hora inexistent (salt de primavera): el viatge d'anada i tornada per UTC no coincideix.
    if dt.astimezone(timezone.utc).astimezone(zona).replace(tzinfo=None) != ingenua:
        dt = dt.astimezone(timezone.utc).astimezone(zona)
    return dt


def _dies_candidats(prog: dict, ara_local: date) -> list[date]:
    """Dies en què hi ha una ocurrència, al voltant de `ara_local` (de més nou a més antic)."""
    t = prog["tipus"]
    if t in UNA_VEGADA:
        return [date.fromisoformat(prog["data"])] if prog.get("data") else []
    if t == "diari":
        return [ara_local + timedelta(days=1 - i) for i in range(3)]
    if t == "setmanal":
        d = ara_local + timedelta(days=(prog["dia_setmana"] - ara_local.weekday()) % 7)
        return [d, d - timedelta(days=7), d - timedelta(days=14)]
    if t == "mensual":
        out, a, m = [], ara_local.year, ara_local.month
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
        for _ in range(3):
            out.append(date(a, m, min(prog["dia_mes"], monthrange(a, m)[1])))
            a, m = (a - 1, 12) if m == 1 else (a, m - 1)
        return out
    raise ValueError(f"Tipus d'informe desconegut: {t}")


def ocurrencies(prog: dict, ara: datetime, zona: str) -> list[datetime]:
    """Ocurrències (en UTC) properes a `ara`, ordenades de més nova a més antiga."""
    tz = ZoneInfo(zona)
    dies = _dies_candidats(prog, ara.astimezone(tz).date())
    return sorted((_local(d, prog["hora"], tz).astimezone(timezone.utc) for d in dies), reverse=True)


def anterior(prog: dict, ara: datetime, zona: str) -> datetime | None:
    """Darrera ocurrència <= `ara` (en UTC), o None."""
    return next((o for o in ocurrencies(prog, ara, zona) if o <= ara.astimezone(timezone.utc)), None)


def propera(prog: dict, ara: datetime, zona: str) -> datetime | None:
    """Propera ocurrència > `ara`, en hora local, o None (una vegada ja passada, o inactiva)."""
    if not prog.get("actiu", 1):
        return None
    futures = [o for o in ocurrencies(prog, ara, zona) if o > ara.astimezone(timezone.utc)]
    return min(futures).astimezone(ZoneInfo(zona)) if futures else None


def toca(prog: dict, ara: datetime, zona: str) -> datetime | None:
    """L'ocurrència que s'ha de generar ara (en hora local), o None.

    `prog` porta `creada` i `darrera_execucio` (ISO amb desplaçament, o None).
    """
    if not prog.get("actiu", 1):
        return None
    o = anterior(prog, ara, zona)
    if o is None:
        return None
    for camp in ("creada", "darrera_execucio"):
        if prog.get(camp) and o <= datetime.fromisoformat(prog[camp]).astimezone(timezone.utc):
            return None
    return o.astimezone(ZoneInfo(zona))


def periode(tipus: str, ocurrencia: date, inici_pilot: date | None = None) -> tuple[date, date]:
    """Període (des, fins) que cobreix l'informe generat el dia `ocurrencia`."""
    ahir = ocurrencia - timedelta(days=1)
    if tipus == "diari":
        return ahir, ahir
    if tipus == "setmanal":
        dilluns = ocurrencia - timedelta(days=ocurrencia.weekday() + 7)
        return dilluns, dilluns + timedelta(days=6)
    if tipus == "mensual":
        fi = ocurrencia.replace(day=1) - timedelta(days=1)
        return fi.replace(day=1), fi
    if tipus == "temporada":
        return ocurrencia - timedelta(days=DIES_TEMPORADA), ahir
    if inici_pilot and inici_pilot <= ahir:
        return inici_pilot, ahir
    return ocurrencia - timedelta(days=DIES_PILOT), ahir


# ---------------------------------------------------------------- Base de dades


def zona_de(con: sqlite3.Connection, botiga_id: str | None) -> str:
    if botiga_id:
        fila = con.execute("SELECT zona_horaria FROM botiga WHERE id = ?", (botiga_id,)).fetchone()
        if fila and fila["zona_horaria"]:
            return fila["zona_horaria"]
    return temps.ZONA_PER_DEFECTE


def programacio_json(con: sqlite3.Connection, fila: sqlite3.Row | dict, ara: datetime | None = None) -> dict:
    """Forma `Programacio` de l'especificació (més `darrera_execucio`)."""
    p = {c: fila[c] for c in CAMPS}
    p["actiu"] = bool(p["actiu"])
    p["destinataris"] = json.loads(fila["destinataris"] or "[]")
    zona = zona_de(con, p["botiga_id"])
    ara = ara or datetime.now(timezone.utc)
    seguent = propera(dict(fila), ara, zona)
    p["propera"] = seguent.isoformat(timespec="seconds") if seguent else None
    p["darrera_execucio"] = fila["darrera_execucio"]
    return p


def programacio(con: sqlite3.Connection, pid: int) -> dict | None:
    fila = con.execute("SELECT * FROM programacio_informe WHERE id = ?", (pid,)).fetchone()
    return programacio_json(con, fila) if fila else None


def lliurat_resum(fila: sqlite3.Row) -> dict:
    """Fila de `GET /informes/lliurats`."""
    return {"id": fila["id"], "tipus": fila["tipus"], "botiga_id": fila["botiga_id"], "des": fila["des"],
            "fins": fila["fins"], "generat": fila["generat"], "estat_enviament": fila["estat_enviament"],
            "enviat_a": json.loads(fila["enviat_a"] or "[]"), "programacio_id": fila["programacio_id"],
            "error": fila["error"]}


def genera(con: sqlite3.Connection, tipus: str, botiga_id: str | None, des: date, fins: date,
           programacio_id: int | None = None, generat: str | None = None) -> int:
    """Calcula l'informe i en desa la instantània. Retorna l'id del lliurat."""
    if tipus not in TIPUS:
        raise ValueError(f"Tipus d'informe desconegut: {tipus}")
    inf = analitica.informe(con, analitica.Filtre(botiga_id, des, fins), tipus)
    p = inf["periode"]   # el diari es retalla al darrer dia
    lid = con.execute(
        """INSERT INTO informe_lliurat (programacio_id, botiga_id, tipus, des, fins, generat, dades_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (programacio_id, botiga_id, tipus, p["des"], p["fins"], generat or temps.ara(zona_de(con, botiga_id)),
         json.dumps(inf, ensure_ascii=False))).lastrowid
    con.commit()
    return lid


def lliurat(con: sqlite3.Connection, lid: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM informe_lliurat WHERE id = ?", (lid,)).fetchone()


def assumpte(inf: dict, botiga_nom: str | None) -> str:
    p = inf.get("periode") or {}
    dates = p.get("des") if p.get("des") == p.get("fins") else f"{p.get('des')} – {p.get('fins')}"
    return f"{inf.get('titol', 'Informe')} · {botiga_nom or 'totes les botigues'} · {dates}"


def envia_informe(con: sqlite3.Connection, cfg: Config, inf: dict, botiga_id: str | None,
                  destinataris: list[str], generat: str | None = None) -> list[str]:
    """Genera el PDF i l'envia. ErrorCorreu (amb el motiu) si no es pot."""
    if not correu.configurat(cfg):
        raise correu.ErrorCorreu("El correu no està configurat")
    destinataris = correu.valida_destinataris(destinataris)
    fila = con.execute("SELECT nom FROM botiga WHERE id = ?", (botiga_id,)).fetchone() if botiga_id else None
    nom = fila["nom"] if fila else None
    acc = (inf.get("accio") or {}).get("text")
    text = (f"Hola,\n\nUs enviem «{inf.get('titol')}» en PDF.\n\n"
            + (f"Acció proposada: {acc}\n\n" if acc else "")
            + "Les xifres es calculen amb les dades de Hebra; el PDF explica què no podem afirmar.\n")
    return correu.envia(cfg, destinataris, assumpte(inf, nom), text,
                        [(informe_pdf.nom_fitxer(inf, botiga_id), informe_pdf.pdf(con, inf, botiga_id, generat),
                          "application/pdf")])


def envia_lliurat(con: sqlite3.Connection, cfg: Config, lid: int, destinataris: list[str]) -> dict:
    """Envia un lliurat i en desa l'estat (enviat o error). Torna a llançar ErrorCorreu o ErrorPdf."""
    f = lliurat(con, lid)
    inf = json.loads(f["dades_json"])
    try:
        enviats = envia_informe(con, cfg, inf, f["botiga_id"], destinataris, f["generat"])
    except (correu.ErrorCorreu, informe_pdf.ErrorPdf) as e:
        con.execute("UPDATE informe_lliurat SET estat_enviament = 'error', error = ? WHERE id = ?", (str(e), lid))
        con.commit()
        raise
    abans = json.loads(f["enviat_a"] or "[]")
    tots = abans + [d for d in enviats if d not in abans]
    con.execute("UPDATE informe_lliurat SET estat_enviament = 'enviat', enviat_a = ?, error = NULL WHERE id = ?",
                (json.dumps(tots), lid))
    con.commit()
    return lliurat_resum(lliurat(con, lid))


def _inici_pilot(con: sqlite3.Connection, botiga_id: str | None) -> date | None:
    fila = con.execute("SELECT MIN(inici) FROM pilot WHERE (? IS NULL OR botiga_id = ?)",
                       (botiga_id, botiga_id)).fetchone()
    return date.fromisoformat(fila[0]) if fila and fila[0] else None


def executa_pendents(con: sqlite3.Connection, cfg: Config, ara: datetime | None = None) -> list[int]:
    """El bucle de fons ho crida cada minut: genera (i envia, si hi ha SMTP) el que toqui. Retorna els lliurats."""
    ara = ara or datetime.now(timezone.utc)
    fets = []
    for fila in con.execute("SELECT * FROM programacio_informe WHERE actiu = 1 ORDER BY id").fetchall():
        prog = dict(fila)
        zona = zona_de(con, prog["botiga_id"])
        o = toca(prog, ara, zona)
        if o is None:
            continue
        des, fins = periode(prog["tipus"], o.date(), _inici_pilot(con, prog["botiga_id"]))
        # Primer es marca l'execució: si el càlcul falla, no es torna a provar cada minut.
        con.execute("UPDATE programacio_informe SET darrera_execucio = ? WHERE id = ?",
                    (o.isoformat(timespec="seconds"), prog["id"]))
        con.commit()
        try:
            lid = genera(con, prog["tipus"], prog["botiga_id"], des, fins, prog["id"])
        except Exception:
            log.exception("No s'ha pogut generar l'informe programat %s", prog["id"])
            continue
        fets.append(lid)
        destinataris = json.loads(prog["destinataris"] or "[]")
        if destinataris and correu.configurat(cfg):
            try:
                envia_lliurat(con, cfg, lid, destinataris)
            except (correu.ErrorCorreu, informe_pdf.ErrorPdf) as e:   # ja queda marcat com a error
                log.warning("Informe %s generat però no enviat: %s", lid, e)
            except Exception as e:   # un error inesperat no ha d'aturar els altres informes que toquen
                log.exception("Informe %s generat però no enviat", lid)
                con.rollback()
                con.execute("UPDATE informe_lliurat SET estat_enviament = 'error', error = ? WHERE id = ?",
                            (f"Error inesperat ({type(e).__name__}): avisa l'equip de Hebra", lid))
                con.commit()
    return fets
