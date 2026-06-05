"""TOTP multi-factor: secret generation, QR provisioning, and recovery codes.

Compatible with any RFC 6238 authenticator app (Google Authenticator, Authy,
1Password, ...). The QR is rendered server-side to a base64 PNG data URI so the
frontend needs no QR library.
"""

import base64
import io
import json
import secrets
from typing import Optional

import pyotp
import qrcode

from .passwords import hash_password, verify_password

ISSUER = "Collectabase"
_RECOVERY_CODE_COUNT = 10


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=ISSUER)


def qr_data_uri(secret: str, account_email: str) -> str:
    img = qrcode.make(provisioning_uri(secret, account_email))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_code(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    # valid_window=1 tolerates ~30s clock drift in either direction.
    return pyotp.TOTP(secret).verify(str(code).strip().replace(" ", ""), valid_window=1)


# --- recovery codes -------------------------------------------------------

def generate_recovery_codes() -> tuple[list[str], str]:
    """Return (plaintext_codes, json_of_hashed_codes). Show plaintext once."""
    plaintext = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(_RECOVERY_CODE_COUNT)]
    hashed = json.dumps([hash_password(code) for code in plaintext])
    return plaintext, hashed


def consume_recovery_code(stored_json: Optional[str], code: str) -> Optional[str]:
    """If `code` matches an unused recovery code, return the updated JSON with
    that code removed; otherwise return None."""
    if not stored_json or not code:
        return None
    try:
        hashes = json.loads(stored_json)
    except (ValueError, TypeError):
        return None
    candidate = str(code).strip()
    for h in hashes:
        if verify_password(candidate, h):
            hashes.remove(h)
            return json.dumps(hashes)
    return None
