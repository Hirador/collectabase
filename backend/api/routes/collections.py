"""Collections and sharing (membership management)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from ...database import get_db
from ...auth.deps import (
    CurrentUser, assert_collection_access, get_current_user,
)

router = APIRouter(prefix="/api/collections", tags=["collections"])

_VALID_ROLES = {"viewer", "editor", "owner"}


class CreateCollectionRequest(BaseModel):
    name: str
    is_personal: bool = False


class RenameCollectionRequest(BaseModel):
    name: str


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: str = "editor"


class UpdateMemberRequest(BaseModel):
    role: str


def _collection_summary(db, collection_id: int, user: CurrentUser) -> dict:
    row = db.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    item_count = db.execute(
        "SELECT COUNT(*) AS n FROM games WHERE collection_id = ?", (collection_id,)
    ).fetchone()
    member_count = db.execute(
        "SELECT COUNT(*) AS n FROM collection_members WHERE collection_id = ?", (collection_id,)
    ).fetchone()
    role_row = db.execute(
        "SELECT role FROM collection_members WHERE collection_id = ? AND user_id = ?",
        (collection_id, user.id),
    ).fetchone()
    return {
        "id": row["id"],
        "name": row["name"],
        "is_personal": bool(row["is_personal"]),
        "owner_user_id": row["owner_user_id"],
        "is_owner": row["owner_user_id"] == user.id,
        "role": role_row["role"] if role_row else ("owner" if user.is_super_admin else None),
        "item_count": int(item_count["n"]),
        "member_count": int(member_count["n"]),
    }


@router.get("")
async def list_collections(user: CurrentUser = Depends(get_current_user)):
    with get_db() as db:
        if user.is_super_admin:
            rows = db.execute("SELECT id FROM collections ORDER BY id").fetchall()
        else:
            rows = db.execute(
                "SELECT collection_id AS id FROM collection_members WHERE user_id = ? ORDER BY collection_id",
                (user.id,),
            ).fetchall()
        return {"collections": [_collection_summary(db, int(r["id"]), user) for r in rows]}


@router.post("")
async def create_collection(payload: CreateCollectionRequest, user: CurrentUser = Depends(get_current_user)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "Name is required."})
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO collections (name, owner_user_id, is_personal) VALUES (?, ?, ?)",
            (name, user.id, 1 if payload.is_personal else 0),
        )
        cid = cur.lastrowid
        db.execute(
            "INSERT INTO collection_members (collection_id, user_id, role) VALUES (?, ?, 'owner')",
            (cid, user.id),
        )
        db.commit()
    return {"ok": True, "id": cid, "name": name}


@router.patch("/{collection_id}")
async def rename_collection(collection_id: int, payload: RenameCollectionRequest,
                            user: CurrentUser = Depends(get_current_user)):
    assert_collection_access(user, collection_id, "owner")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail={"code": "invalid", "message": "Name is required."})
    with get_db() as db:
        db.execute("UPDATE collections SET name = ? WHERE id = ?", (name, collection_id))
        db.commit()
    return {"ok": True}


@router.delete("/{collection_id}")
async def delete_collection(collection_id: int, user: CurrentUser = Depends(get_current_user)):
    assert_collection_access(user, collection_id, "owner")
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) AS n FROM collections").fetchone()
        if int(total["n"]) <= 1:
            raise HTTPException(status_code=400, detail={
                "code": "last_collection", "message": "You can't delete your only collection."})
        # FK ON DELETE CASCADE removes games/lots/value_history + memberships.
        db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        db.commit()
    return {"ok": True}


# --- members --------------------------------------------------------------

@router.get("/{collection_id}/members")
async def list_members(collection_id: int, user: CurrentUser = Depends(get_current_user)):
    assert_collection_access(user, collection_id, "viewer")
    with get_db() as db:
        rows = db.execute(
            "SELECT m.user_id, m.role, u.email, u.display_name "
            "FROM collection_members m JOIN users u ON u.id = m.user_id "
            "WHERE m.collection_id = ? ORDER BY m.role DESC, u.email",
            (collection_id,),
        ).fetchall()
    return {"members": [
        {"user_id": r["user_id"], "email": r["email"],
         "display_name": r["display_name"], "role": r["role"]}
        for r in rows
    ]}


@router.post("/{collection_id}/members")
async def add_member(collection_id: int, payload: AddMemberRequest,
                     user: CurrentUser = Depends(get_current_user)):
    assert_collection_access(user, collection_id, "owner")
    if payload.role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail={"code": "invalid_role", "message": "Unknown role."})
    with get_db() as db:
        target = db.execute(
            "SELECT id FROM users WHERE lower(email) = lower(?)", (str(payload.email).strip(),)
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail={
                "code": "user_not_found",
                "message": "No user with that email. A super admin must create the account first."})
        db.execute(
            "INSERT INTO collection_members (collection_id, user_id, role) VALUES (?, ?, ?) "
            "ON CONFLICT(collection_id, user_id) DO UPDATE SET role = excluded.role",
            (collection_id, target["id"], payload.role),
        )
        db.commit()
    return {"ok": True}


@router.patch("/{collection_id}/members/{member_user_id}")
async def update_member(collection_id: int, member_user_id: int, payload: UpdateMemberRequest,
                        user: CurrentUser = Depends(get_current_user)):
    assert_collection_access(user, collection_id, "owner")
    if payload.role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail={"code": "invalid_role", "message": "Unknown role."})
    with get_db() as db:
        owner = db.execute(
            "SELECT owner_user_id FROM collections WHERE id = ?", (collection_id,)
        ).fetchone()
        if owner and owner["owner_user_id"] == member_user_id and payload.role != "owner":
            raise HTTPException(status_code=400, detail={
                "code": "cannot_demote_owner",
                "message": "Transfer ownership before changing the owner's role."})
        db.execute(
            "UPDATE collection_members SET role = ? WHERE collection_id = ? AND user_id = ?",
            (payload.role, collection_id, member_user_id),
        )
        db.commit()
    return {"ok": True}


@router.delete("/{collection_id}/members/{member_user_id}")
async def remove_member(collection_id: int, member_user_id: int,
                        user: CurrentUser = Depends(get_current_user)):
    # Owners can remove anyone; a member may remove themselves (leave).
    if member_user_id != user.id:
        assert_collection_access(user, collection_id, "owner")
    with get_db() as db:
        owner = db.execute(
            "SELECT owner_user_id FROM collections WHERE id = ?", (collection_id,)
        ).fetchone()
        if owner and owner["owner_user_id"] == member_user_id:
            raise HTTPException(status_code=400, detail={
                "code": "cannot_remove_owner",
                "message": "The owner can't be removed. Transfer ownership or delete the collection."})
        db.execute(
            "DELETE FROM collection_members WHERE collection_id = ? AND user_id = ?",
            (collection_id, member_user_id),
        )
        db.commit()
    return {"ok": True}
