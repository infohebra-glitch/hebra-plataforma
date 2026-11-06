"""Dependències comunes de l'API v2: connexió, usuari de la sessió, rols i filtre."""

import sqlite3
from datetime import date, timedelta

from fastapi import Depends, HTTPException, Request

from hebra import analitica, auth

BOTIGA_O_MES = ("admin", "marca", "botiga")
MARCA_O_MES = ("admin", "marca")
NOMES_ADMIN = ("admin",)


def bd(request: Request) -> sqlite3.Connection:
    return request.app.state.con


def usuari(request: Request) -> dict:
    """Usuari de la galeta de sessió, o 401."""
    testimoni = request.cookies.get(auth.NOM_GALETA, "")
    uid = auth.verifica(request.app.state.cfg.secret, testimoni) if testimoni else None
    fila = auth.usuari_per_id(request.app.state.con, uid) if uid is not None else None
    if fila is None:
        raise HTTPException(401, "Cal iniciar la sessió")
    return auth.usuari_json(fila)


def rol(*rols: str):
    """Dependència que exigeix un dels rols (403 si no)."""
    def comprova(u: dict = Depends(usuari)) -> dict:
        if u["rol"] not in rols:
            raise HTTPException(403, "No tens permís per a aquesta acció")
        return u
    return comprova


def botiga_permesa(con: sqlite3.Connection, u: dict, botiga: str | None) -> str | None:
    """Botiga efectiva: un usuari de botiga només veu la seva (403 si en demana una altra)."""
    if u["rol"] == "botiga":
        if botiga and botiga != u["botiga_id"]:
            raise HTTPException(403, "Només pots veure la teva botiga")
        return u["botiga_id"]
    if botiga and not con.execute("SELECT 1 FROM botiga WHERE id = ?", (botiga,)).fetchone():
        raise HTTPException(404, f"Botiga desconeguda: {botiga}")
    return botiga or None


def comprova_botiga(u: dict, botiga_id: str | None) -> None:
    """Per a escriptures: un usuari de botiga només pot tocar dades de la seva botiga."""
    if u["rol"] == "botiga" and botiga_id != u["botiga_id"]:
        raise HTTPException(403, "Només pots modificar dades de la teva botiga")


def data(text: str | None, nom: str) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise HTTPException(400, f"Data no vàlida a «{nom}» (format AAAA-MM-DD)")


def darrer_dia_amb_dades(con: sqlite3.Connection, botiga: str | None) -> date:
    fila = con.execute(
        """SELECT MAX(substr(s.inici, 1, 10)) FROM sessio s JOIN cabina c ON c.id = s.cabina_id
           WHERE (? IS NULL OR c.botiga_id = ?)""", (botiga, botiga)).fetchone()[0]
    if not fila:
        fila = con.execute("SELECT MAX(data) FROM venda_linia WHERE (? IS NULL OR botiga_id = ?)",
                           (botiga, botiga)).fetchone()[0]
    return date.fromisoformat(fila) if fila else date.today()


def filtre(request: Request, botiga: str | None = None, des: str | None = None, fins: str | None = None,
           u: dict = Depends(usuari)) -> analitica.Filtre:
    """Filtre comú (docs/API.md): per defecte, els darrers 7 dies amb dades."""
    con = request.app.state.con
    b = botiga_permesa(con, u, botiga)
    d_des, d_fins = data(des, "des"), data(fins, "fins")
    if d_fins is None:
        d_fins = d_des + timedelta(days=6) if d_des else darrer_dia_amb_dades(con, b)
    if d_des is None:
        d_des = d_fins - timedelta(days=6)
    if d_des > d_fins:
        raise HTTPException(400, "«des» ha de ser anterior o igual a «fins»")
    return analitica.Filtre(b, d_des, d_fins)
