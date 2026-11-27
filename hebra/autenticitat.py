"""Peça original o imitació: verificació del xip NFC (NXP NTAG 424 DNA, «SUN»).

Un adhesiu NFC normal guarda un enllaç fix: qualsevol el pot copiar en un altre adhesiu. Un NTAG 424 DNA
afegeix a l'enllaç, a cada toc, dues dades que canvien sempre:

  picc  = UID del xip + comptador de tocs, xifrats amb AES-128 (clau «meta», compartida)
  cmac  = signatura de 8 bytes amb una clau pròpia de cada xip, que no es pot llegir del xip

La plataforma desxifra `picc`, comprova que l'UID és el del xip registrat per a aquella peça, recalcula la
signatura i mira que el comptador sigui més alt que l'últim vist. Si tot quadra: «Peça original verificada».
Un enllaç copiat repeteix el mateix comptador; un adhesiu normal amb l'enllaç no porta signatura. En tots dos
casos la fitxa ho diu.

Algorisme: NXP AN12196 (SDM amb PICCData xifrat i CMAC sobre entrada buida). Les claus de cada xip es deriven
d'una clau mestra aleatòria de la plataforma (taula `parametre`, xifrada amb HEBRA_SECRET), així no se'n guarda
cap en clar a la base de dades. Cap dada de la persona que toca: només el xip.

Estats (`estat`):
  original         signatura bona i comptador nou
  repetit          signatura bona però comptador ja vist (enllaç copiat o reenviat)
  no_verificada    signatura dolenta, UID d'un altre xip o dades il·legibles
  sense_signatura  la peça té xip protegit però l'enllaç no porta signatura (adhesiu copiat)
  None             la peça no té xip protegit (adhesiu normal): la fitxa no diu res
"""

import secrets
import sqlite3

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.cmac import CMAC

from . import db
from .integracions import xifratge

CLAU_PARAMETRE = "nfc_clau_mestra"
ESTATS = ("original", "repetit", "no_verificada", "sense_signatura")
VERIFICADA = "original"
MINUTS_SESSIO = 30   # dins la mateixa visita (canvi d'idioma, formularis) es manté el resultat del toc


class ErrorXip(Exception):
    pass


# ---------------------------------------------------------------- AES / CMAC (AN12196)

def _cmac(clau: bytes, dades: bytes) -> bytes:
    c = CMAC(algorithms.AES(clau))
    c.update(dades)
    return c.finalize()


def _aes(clau: bytes, dades: bytes, xifra: bool) -> bytes:
    c = Cipher(algorithms.AES(clau), modes.CBC(bytes(16)))
    op = c.encryptor() if xifra else c.decryptor()
    return op.update(dades) + op.finalize()


def desxifra_picc(clau_meta: bytes, picc_hex: str) -> tuple[bytes, int] | None:
    """(UID de 7 bytes, comptador) o None si no és un PICCData vàlid."""
    try:
        dades = bytes.fromhex(picc_hex)
    except ValueError:
        return None
    if len(dades) != 16:
        return None
    clar = _aes(clau_meta, dades, xifra=False)
    if clar[0] != 0xC7:   # UID i comptador presents, UID de 7 bytes
        return None
    return clar[1:8], int.from_bytes(clar[8:11], "little")


def signatura(clau_fitxer: bytes, uid: bytes, comptador: int) -> bytes:
    """SDMMAC: CMAC de l'entrada buida amb la clau de sessió, quedant-nos els bytes senars (8 bytes)."""
    sv2 = bytes([0x3C, 0xC3, 0x00, 0x01, 0x00, 0x80]) + uid + comptador.to_bytes(3, "little")
    clau_sessio = _cmac(clau_fitxer, sv2)
    return _cmac(clau_sessio, b"")[1::2]


def xifra_picc(clau_meta: bytes, uid: bytes, comptador: int) -> str:
    clar = bytes([0xC7]) + uid + comptador.to_bytes(3, "little") + secrets.token_bytes(5)
    return _aes(clau_meta, clar, xifra=True).hex().upper()


# ---------------------------------------------------------------- Claus de la plataforma

def clau_mestra(con: sqlite3.Connection, secret_app: str) -> bytes:
    """Clau mestra (16 bytes). Es crea la primera vegada; es desa xifrada amb HEBRA_SECRET."""
    desada = db.parametre(con, None, CLAU_PARAMETRE)
    if desada:
        return bytes.fromhex(xifratge.desxifra(secret_app, desada))
    nova = secrets.token_bytes(16)
    db.desa_parametre(con, "*", CLAU_PARAMETRE, xifratge.xifra(secret_app, nova.hex()))
    return nova


def clau_meta(mestra: bytes) -> bytes:
    return _cmac(mestra, b"\x01hebra-nfc-meta")


def clau_fitxer(mestra: bytes, uid: bytes) -> bytes:
    return _cmac(mestra, b"\x02hebra-nfc-fitxer" + uid)


# ---------------------------------------------------------------- Registre i verificació

def _uid(text: str) -> bytes:
    try:
        uid = bytes.fromhex(text.replace(":", "").replace(" ", ""))
    except ValueError:
        raise ErrorXip(f"UID no vàlid: {text}") from None
    if len(uid) != 7:
        raise ErrorXip("L'UID d'un NTAG 424 DNA té 7 bytes (14 caràcters hex)")
    return uid


def _etiqueta(con: sqlite3.Connection, epc: str | None, model: str | None) -> sqlite3.Row:
    if epc:
        fila = con.execute("SELECT * FROM etiqueta WHERE epc = ?", (epc,)).fetchone()
    else:
        fila = con.execute("""SELECT e.* FROM etiqueta e JOIN catalog_sku k ON k.gtin = e.gtin
                              WHERE lower(k.model) = lower(?) ORDER BY e.rowid LIMIT 1""", (model,)).fetchone()
    if not fila:
        raise ErrorXip(f"No hi ha cap etiqueta {'amb EPC ' + epc if epc else 'del model ' + str(model)}")
    return fila


def protegeix(con: sqlite3.Connection, secret_app: str, uid_text: str, epc: str | None = None,
              model: str | None = None, simulat: bool = False) -> dict:
    """Associa un xip NTAG 424 DNA (UID) a la peça i torna les claus que s'han de gravar al xip."""
    uid = _uid(uid_text)
    et = _etiqueta(con, epc, model)
    altra = con.execute("SELECT epc FROM etiqueta WHERE nfc_uid = ? AND epc <> ?", (uid.hex().upper(), et["epc"])).fetchone()
    if altra:
        raise ErrorXip(f"Aquest xip ja és d'una altra peça ({altra['epc']})")
    con.execute("UPDATE etiqueta SET nfc_uid = ?, nfc_ctr = -1, nfc_simulat = ? WHERE epc = ?",
                (uid.hex().upper(), int(simulat), et["epc"]))
    con.commit()
    m = clau_mestra(con, secret_app)
    return {"epc": et["epc"], "token": et["nfc_token"], "uid": uid.hex().upper(),
            "clau_meta": clau_meta(m).hex().upper(), "clau_fitxer": clau_fitxer(m, uid).hex().upper()}


def toc_simulat(con: sqlite3.Connection, secret_app: str, epc: str | None = None, model: str | None = None) -> dict:
    """Fa el que faria el xip en un toc (per a la demo i les proves): picc i cmac del comptador següent.
    Si la peça no té xip, n'hi posa un de simulat (que no avisa quan s'obre l'adhesiu normal)."""
    et = _etiqueta(con, epc, model)
    if not et["nfc_uid"]:
        protegeix(con, secret_app, "04" + secrets.token_hex(6), epc=et["epc"], simulat=True)
        et = _etiqueta(con, et["epc"], None)
    m = clau_mestra(con, secret_app)
    uid = bytes.fromhex(et["nfc_uid"])
    # El següent al més alt entre l'últim verificat i l'últim generat (es poden generar dos enllaços seguits).
    ctr = max(et["nfc_ctr"], et["nfc_ctr_simulat"]) + 1
    con.execute("UPDATE etiqueta SET nfc_ctr_simulat = ? WHERE epc = ?", (ctr, et["epc"]))
    con.commit()
    return {"epc": et["epc"], "token": et["nfc_token"], "picc": xifra_picc(clau_meta(m), uid, ctr),
            "cmac": signatura(clau_fitxer(m, uid), uid, ctr).hex().upper(), "comptador": ctr}


def verifica(con: sqlite3.Connection, secret_app: str, peca: sqlite3.Row, picc: str | None, cmac: str | None,
             desa: bool = True) -> str | None:
    """Estat del toc (vegeu el docstring del mòdul). `desa=False` no mou el comptador (robots, previsualitzacions)."""
    uid_desat = peca["nfc_uid"] if "nfc_uid" in peca.keys() else None
    if not uid_desat:
        return None
    if not picc or not cmac:
        return None if peca["nfc_simulat"] else "sense_signatura"
    m = clau_mestra(con, secret_app)
    res = desxifra_picc(clau_meta(m), picc)
    if res is None:
        return "no_verificada"
    uid, ctr = res
    if uid.hex().upper() != uid_desat:
        return "no_verificada"
    try:
        rebuda = bytes.fromhex(cmac)
    except ValueError:
        return "no_verificada"
    if not secrets.compare_digest(rebuda, signatura(clau_fitxer(m, uid), uid, ctr)):
        return "no_verificada"
    if ctr <= peca["nfc_ctr"]:
        return "repetit"
    if desa:
        # Només avança si ningú no l'ha avançat entretant (dos tocs alhora no poden ser tots dos «original»).
        cur = con.execute("UPDATE etiqueta SET nfc_ctr = ? WHERE epc = ? AND nfc_ctr < ?", (ctr, peca["epc"], ctr))
        con.commit()
        if not cur.rowcount:
            return "repetit"
    return VERIFICADA


def estat_de_la_visita(con: sqlite3.Connection, sessio_nfc: str, gtin: str, ara: str) -> str | None:
    """El resultat del toc que va obrir aquesta visita (mateixa sessió i peça, darrers `MINUTS_SESSIO`)."""
    fila = con.execute(
        """SELECT valor FROM esdeveniment_nfc WHERE sessio_nfc = ? AND gtin = ? AND tipus = 'verificacio'
           AND julianday(ts) >= julianday(?) - ? / 1440.0 ORDER BY id DESC LIMIT 1""",
        (sessio_nfc, gtin, ara, MINUTS_SESSIO)).fetchone()
    return fila["valor"] if fila else None
