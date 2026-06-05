"""JWT access/refresh tokens + the signing secret.

The secret comes from the JWT_SECRET env var if set; otherwise a random one is
generated once and persisted in app_meta so tokens survive restarts (and so the
admin never has to manage a secret for a home deployment).
"""

import os
import secrets
import time
from typing import Any, Optional

import jwt

ACCESS_TTL_SECONDS = 30 * 60            # 30 minutes
REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
ALGORITHM = "HS256"

_cached_secret: Optional[str] = None


def _get_secret() -> str:
    global _cached_secret
    if _cached_secret:
        return _cached_secret

    env_secret = os.getenv("JWT_SECRET", "").strip()
    if env_secret:
        _cached_secret = env_secret
        return _cached_secret

    # Persist a generated secret so restarts don't invalidate everyone's sessions.
    from ..database import get_app_meta, set_app_meta

    stored = get_app_meta("cfg:jwt_secret")
    if stored:
        _cached_secret = stored
        return _cached_secret

    generated = secrets.token_urlsafe(48)
    set_app_meta("cfg:jwt_secret", generated)
    _cached_secret = generated
    return _cached_secret


def create_access_token(*, user_id: int, token_version: int, is_super_admin: bool, csrf: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "tv": token_version,
        "sa": bool(is_super_admin),
        "csrf": csrf,
        "type": "access",
        "iat": now,
        "exp": now + ACCESS_TTL_SECONDS,
    }
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM)


def create_refresh_token(*, user_id: int, token_version: int) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "tv": token_version,
        "type": "refresh",
        "iat": now,
        "exp": now + REFRESH_TTL_SECONDS,
    }
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)
