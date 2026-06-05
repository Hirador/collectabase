"""Password and recovery-code hashing (bcrypt).

bcrypt silently truncates input past 72 bytes, so we pre-hash to a fixed-length
base64 digest first — this lets arbitrarily long passwords stay fully significant.
"""

import base64
import hashlib

import bcrypt


def _prehash(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
