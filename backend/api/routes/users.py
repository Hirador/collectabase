"""Super-admin user management (create/list/update/disable users)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ...database import get_db
from ...auth.deps import CurrentUser, require_super_admin
from ...auth.passwords import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


class CreateUserRequest(BaseModel):
    email: EmailStr
    display_name: str | None = None
    password: str = Field(min_length=8)
    is_super_admin: bool = False
    mfa_required: bool = False


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None
    is_super_admin: bool | None = None
    mfa_required: bool | None = None
    new_password: str | None = Field(default=None, min_length=8)


def _user_row(row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "is_super_admin": bool(row["is_super_admin"]),
        "is_active": bool(row["is_active"]),
        "mfa_enabled": bool(row["mfa_enabled"]),
        "mfa_required": bool(row["is_super_admin"] or row["mfa_required"]),
        "last_login_at": row["last_login_at"],
        "created_at": row["created_at"],
    }


def _count_active_super_admins(db, exclude_id: int | None = None) -> int:
    if exclude_id is None:
        row = db.execute(
            "SELECT COUNT(*) AS n FROM users WHERE is_super_admin = 1 AND is_active = 1"
        ).fetchone()
    else:
        row = db.execute(
            "SELECT COUNT(*) AS n FROM users WHERE is_super_admin = 1 AND is_active = 1 AND id != ?",
            (exclude_id,),
        ).fetchone()
    return int(row["n"]) if row else 0


@router.get("")
async def list_users(_admin: CurrentUser = Depends(require_super_admin)):
    with get_db() as db:
        rows = db.execute("SELECT * FROM users ORDER BY id").fetchall()
    return {"users": [_user_row(r) for r in rows]}


@router.post("")
async def create_user(payload: CreateUserRequest, _admin: CurrentUser = Depends(require_super_admin)):
    email = str(payload.email).strip()
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE lower(email) = lower(?)", (email,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail={
                "code": "email_taken", "message": "A user with that email already exists."})
        cur = db.execute(
            "INSERT INTO users (email, display_name, password_hash, is_super_admin, is_active, mfa_required) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (email, (payload.display_name or "").strip() or None,
             hash_password(payload.password), 1 if payload.is_super_admin else 0,
             1 if payload.mfa_required else 0),
        )
        db.commit()
        new_id = cur.lastrowid
    return {"ok": True, "id": new_id, "email": email}


@router.patch("/{user_id}")
async def update_user(user_id: int, payload: UpdateUserRequest,
                      admin: CurrentUser = Depends(require_super_admin)):
    with get_db() as db:
        target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "User not found."})

        # Guard against removing the last super admin / locking yourself out.
        demoting = payload.is_super_admin is False and bool(target["is_super_admin"])
        deactivating = payload.is_active is False and bool(target["is_active"])
        if (demoting or deactivating) and bool(target["is_super_admin"]):
            if _count_active_super_admins(db, exclude_id=user_id) == 0:
                raise HTTPException(status_code=400, detail={
                    "code": "last_super_admin",
                    "message": "Can't remove the last active super admin."})

        sets, params = [], []
        if payload.display_name is not None:
            sets.append("display_name = ?"); params.append(payload.display_name.strip() or None)
        if payload.is_active is not None:
            sets.append("is_active = ?"); params.append(1 if payload.is_active else 0)
        if payload.is_super_admin is not None:
            sets.append("is_super_admin = ?"); params.append(1 if payload.is_super_admin else 0)
        if payload.mfa_required is not None:
            sets.append("mfa_required = ?"); params.append(1 if payload.mfa_required else 0)
        if payload.new_password is not None:
            sets.append("password_hash = ?"); params.append(hash_password(payload.new_password))
            # Force re-login everywhere when an admin resets a password.
            sets.append("token_version = token_version + 1")
        if not sets:
            return {"ok": True, "updated": []}
        params.append(user_id)
        db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", tuple(params))
        db.commit()
    return {"ok": True}


@router.delete("/{user_id}")
async def delete_user(user_id: int, admin: CurrentUser = Depends(require_super_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail={
            "code": "cannot_delete_self", "message": "You can't delete your own account."})
    with get_db() as db:
        target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "User not found."})
        if bool(target["is_super_admin"]) and _count_active_super_admins(db, exclude_id=user_id) == 0:
            raise HTTPException(status_code=400, detail={
                "code": "last_super_admin", "message": "Can't delete the last active super admin."})
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
    return {"ok": True}
