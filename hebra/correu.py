"""Enviament de correus (informes en PDF) amb `smtplib` i STARTTLS.

Configuració per variables d'entorn (hebra/config.py): HEBRA_SMTP_HOST,
HEBRA_SMTP_PORT (587), HEBRA_SMTP_USUARI, HEBRA_SMTP_CONTRASENYA i
HEBRA_SMTP_REMITENT. Sense host, `configurat` és fals i `envia` no fa res.

Privacitat: els destinataris són sempre persones de l'EQUIP de la marca o de la
botiga (els informes programats i el botó «Envia per correu»). Mai s'envia res a
clients finals: la plataforma no en desa cap correu.
"""

import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from .config import Config

# Prou estricte per detectar errors de tecleig; no pretén validar tot l'RFC 5322.
_CORREU = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
MAX_DESTINATARIS = 20
TIMEOUT_S = 30


class ErrorCorreu(Exception):
    """Error amb un missatge en català que es pot ensenyar a l'usuari."""


def configurat(cfg: Config) -> bool:
    return bool(cfg.smtp_host)


def valida_destinataris(destinataris: list[str]) -> list[str]:
    """Neteja (espais, duplicats) i valida la llista. ErrorCorreu si n'hi ha cap de no vàlid."""
    nets: list[str] = []
    for d in destinataris or []:
        d = (d or "").strip()
        if not d:
            continue
        if not _CORREU.match(d) or len(d) > 254:
            raise ErrorCorreu(f"Correu no vàlid: {d}")
        if d.lower() not in (x.lower() for x in nets):
            nets.append(d)
    if not nets:
        raise ErrorCorreu("Cal almenys un destinatari")
    if len(nets) > MAX_DESTINATARIS:
        raise ErrorCorreu(f"Massa destinataris (màxim {MAX_DESTINATARIS})")
    return nets


def envia(cfg: Config, destinataris: list[str], assumpte: str, text: str,
          adjunts: list[tuple[str, bytes, str]] = ()) -> list[str]:
    """Envia un correu de text amb adjunts [(nom, contingut, tipus MIME)]. Retorna els destinataris.

    ErrorCorreu si no hi ha SMTP configurat, si un correu no és vàlid o si el servidor falla.
    """
    if not configurat(cfg):
        raise ErrorCorreu("El correu no està configurat")
    destinataris = valida_destinataris(destinataris)
    remitent = cfg.smtp_remitent or cfg.smtp_usuari
    if not remitent:
        raise ErrorCorreu("El correu no està configurat (falta HEBRA_SMTP_REMITENT)")
    m = EmailMessage()
    m["From"] = remitent
    m["To"] = ", ".join(destinataris)
    m["Subject"] = assumpte
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=cfg.smtp_host)
    m.set_content(text)
    for nom, contingut, mime in adjunts:
        principal, _, sub = mime.partition("/")
        m.add_attachment(contingut, maintype=principal, subtype=sub or "octet-stream", filename=nom)
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=TIMEOUT_S) as s:
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
            s.ehlo()
            if cfg.smtp_usuari:
                s.login(cfg.smtp_usuari, cfg.smtp_contrasenya)
            s.send_message(m)
    except (smtplib.SMTPException, OSError) as e:
        raise ErrorCorreu(f"No s'ha pogut enviar el correu: {e}") from e
    return destinataris
