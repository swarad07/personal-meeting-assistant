import base64
import json
from typing import Any

from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.encryption_key.encode()
    if len(key) < 32:
        key = key.ljust(32, b"0")
    key = base64.urlsafe_b64encode(key[:32])
    return Fernet(key)


def encrypt_tokens(tokens: dict[str, Any]) -> str:
    f = _get_fernet()
    return f.encrypt(json.dumps(tokens).encode()).decode()


def decrypt_tokens(encrypted: str) -> dict[str, Any]:
    f = _get_fernet()
    return json.loads(f.decrypt(encrypted.encode()).decode())
