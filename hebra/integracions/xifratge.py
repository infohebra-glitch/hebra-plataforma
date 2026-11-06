"""Xifratge dels secrets de les integracions (testimonis d'accés, capçaleres d'autorització).

Fernet (AES-128-CBC + HMAC-SHA256) amb una clau derivada de HEBRA_SECRET per HKDF-SHA256.
Si es canvia HEBRA_SECRET, els secrets desats ja no es poden llegir: cal tornar-los a entrar.
"""

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SAL = b"hebra-integracions"
INFO = b"secret-integracio-v1"


class SecretIllegible(Exception):
    pass


def _fernet(secret_app: str) -> Fernet:
    if not secret_app:
        raise ValueError("Cal HEBRA_SECRET per xifrar els secrets de les integracions")
    clau = HKDF(algorithm=hashes.SHA256(), length=32, salt=SAL, info=INFO).derive(secret_app.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(clau))


def xifra(secret_app: str, text: str) -> str:
    return _fernet(secret_app).encrypt(text.encode("utf-8")).decode("ascii")


def desxifra(secret_app: str, xifrat: str) -> str:
    try:
        return _fernet(secret_app).decrypt(xifrat.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        raise SecretIllegible("No es pot llegir el secret desat (ha canviat HEBRA_SECRET?): torna'l a entrar") from e
