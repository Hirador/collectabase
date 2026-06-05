"""FastAPI dependencies for authentication and authorization.

Auth model:
  - Identity comes from the httpOnly `cb_access` JWT cookie.
  - On unsafe methods (POST/PUT/PATCH/DELETE) we additionally require the
    `X-CSRF-Token` header to equal the token's `csrf` claim (double-submit).
  - Two authorization layers: global (super_admin) and per-collection role
    (owner > editor > viewer).
"""

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request

from ..database import get_db
from .cookies import ACCESS_COOKIE, CSRF_COOKIE
from .tokens import decode_token

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}


@dataclass
class CurrentUser:
    id: int
    email: str
    display_name: Optional[str]
    is_super_admin: bool
    token_version: int


def _unauthorized(message: str = "Not authenticated.") -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "unauthorized", "message": message})


def _forbidden(message: str = "You don't have access to this resource.") -> HTTPException:
    return HTTPException(status_code=403, detail={"code": "forbidden", "message": message})


def _load_user(user_id: int) -> Optional[dict]:
    with get_db() as db:
        row = db.execute(
            "SELECT id, email, display_name, is_super_admin, is_active, token_version "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row.items()) if row else None


async def get_current_user(request: Request) -> CurrentUser:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise _unauthorized()

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise _unauthorized("Invalid or expired session.")

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise _unauthorized("Invalid session.")

    user = _load_user(user_id)
    if not user or not user["is_active"]:
        raise _unauthorized("Account not found or disabled.")
    if int(user["token_version"]) != int(payload.get("tv", -1)):
        raise _unauthorized("Session has been revoked. Please log in again.")

    # Double-submit CSRF on state-changing requests.
    if request.method in _UNSAFE_METHODS:
        header = request.headers.get("x-csrf-token", "")
        cookie = request.cookies.get(CSRF_COOKIE, "")
        if not header or header != payload.get("csrf") or header != cookie:
            raise _forbidden("Invalid or missing CSRF token.")

    return CurrentUser(
        id=user["id"],
        email=user["email"],
        display_name=user["display_name"],
        is_super_admin=bool(user["is_super_admin"]),
        token_version=int(user["token_version"]),
    )


async def require_super_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_super_admin:
        raise _forbidden("Super admin privileges required.")
    return user


# --- per-collection authorization ----------------------------------------

def member_role(user_id: int, collection_id: int) -> Optional[str]:
    """The user's role in a collection, or None if not a member."""
    with get_db() as db:
        row = db.execute(
            "SELECT role FROM collection_members WHERE user_id = ? AND collection_id = ?",
            (user_id, collection_id),
        ).fetchone()
    return row["role"] if row else None


def accessible_collection_ids(user: CurrentUser) -> list[int]:
    """All collection ids the user can read. Super admin sees everything."""
    with get_db() as db:
        if user.is_super_admin:
            rows = db.execute("SELECT id FROM collections").fetchall()
        else:
            rows = db.execute(
                "SELECT collection_id AS id FROM collection_members WHERE user_id = ?",
                (user.id,),
            ).fetchall()
    return [int(r["id"]) for r in rows]


def assert_collection_access(user: CurrentUser, collection_id: int, min_role: str = "viewer") -> str:
    """Ensure the user has at least `min_role` in the collection. Returns the
    effective role. Super admin is treated as owner of every collection."""
    if user.is_super_admin:
        return "owner"
    role = member_role(user.id, collection_id)
    if role is None:
        raise _forbidden("You are not a member of this collection.")
    if _ROLE_RANK.get(role, 0) < _ROLE_RANK.get(min_role, 99):
        raise _forbidden(f"This action requires '{min_role}' access.")
    return role
