"""Authentication & account endpoints (login, MFA, session, bootstrap)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from ...database import get_db
from ...auth.cookies import clear_auth_cookies, set_auth_cookies
from ...auth.deps import CurrentUser, get_current_user
from ...auth.passwords import hash_password, verify_password
from ...auth import tokens
from ...auth import totp

router = APIRouter(prefix="/api/auth", tags=["auth"])

DEFAULT_COLLECTION_ID = 1


# --- payloads -------------------------------------------------------------

class BootstrapRequest(BaseModel):
    email: EmailStr
    display_name: str | None = None
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    code: str | None = None  # TOTP or recovery code


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class MfaVerifyRequest(BaseModel):
    code: str


class MfaDisableRequest(BaseModel):
    password: str


# --- helpers --------------------------------------------------------------

def _users_exist() -> bool:
    with get_db() as db:
        row = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()
    return bool(row and int(row["n"]) > 0)


def _get_user_by_email(email: str) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?)", (email.strip(),)
        ).fetchone()
    return dict(row.items()) if row else None


def _get_user(user_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row.items()) if row else None


def _issue_session(response: Response, user: dict) -> None:
    """Mint access+refresh+csrf, set cookies, and stamp last_login_at."""
    csrf = tokens.new_csrf_token()
    access = tokens.create_access_token(
        user_id=user["id"], token_version=int(user["token_version"]),
        is_super_admin=bool(user["is_super_admin"]), csrf=csrf,
    )
    refresh = tokens.create_refresh_token(
        user_id=user["id"], token_version=int(user["token_version"]),
    )
    set_auth_cookies(response, access_token=access, refresh_token=refresh, csrf=csrf)
    with get_db() as db:
        db.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
        db.commit()


def _user_public(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "is_super_admin": bool(user["is_super_admin"]),
        "mfa_enabled": bool(user["mfa_enabled"]),
    }


# --- bootstrap (first-run super admin) ------------------------------------

@router.get("/bootstrap")
async def bootstrap_status():
    """Frontend shows a 'create super admin' screen while this is true."""
    return {"needs_setup": not _users_exist()}


@router.post("/bootstrap")
async def bootstrap_create(payload: BootstrapRequest, response: Response):
    if _users_exist():
        raise HTTPException(status_code=409, detail={
            "code": "already_initialized", "message": "Setup has already been completed."})

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO users (email, display_name, password_hash, is_super_admin, is_active) "
            "VALUES (?, ?, ?, 1, 1)",
            (str(payload.email).strip(), (payload.display_name or "").strip() or None,
             hash_password(payload.password)),
        )
        user_id = cur.lastrowid
        # Claim the default collection (#1, created ownerless by migration) and
        # add an owner membership so the existing data is now owned + shareable.
        db.execute(
            "UPDATE collections SET owner_user_id = ? WHERE id = ? AND owner_user_id IS NULL",
            (user_id, DEFAULT_COLLECTION_ID),
        )
        db.execute(
            "INSERT OR IGNORE INTO collection_members (collection_id, user_id, role) VALUES (?, ?, 'owner')",
            (DEFAULT_COLLECTION_ID, user_id),
        )
        db.commit()

    user = _get_user(user_id)
    _issue_session(response, user)
    return {"ok": True, "user": _user_public(user)}


# --- login / logout / refresh ---------------------------------------------

@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    user = _get_user_by_email(str(payload.email))
    invalid = HTTPException(status_code=401, detail={
        "code": "invalid_credentials", "message": "Incorrect email or password."})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise invalid
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail={
            "code": "account_disabled", "message": "This account has been disabled."})

    if user["mfa_enabled"]:
        code = (payload.code or "").strip()
        if not code:
            raise HTTPException(status_code=401, detail={
                "code": "mfa_required", "message": "Authenticator code required."})
        if totp.verify_code(user["mfa_secret"], code):
            pass
        else:
            updated = totp.consume_recovery_code(user["mfa_recovery_codes"], code)
            if updated is None:
                raise HTTPException(status_code=401, detail={
                    "code": "mfa_invalid", "message": "Invalid authenticator or recovery code."})
            with get_db() as db:
                db.execute("UPDATE users SET mfa_recovery_codes = ? WHERE id = ?", (updated, user["id"]))
                db.commit()

    _issue_session(response, user)
    return {"ok": True, "user": _user_public(user)}


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    """Mint a fresh session from the (httpOnly) refresh cookie."""
    from ...auth.cookies import REFRESH_COOKIE

    token = request.cookies.get(REFRESH_COOKIE)
    expired = HTTPException(status_code=401, detail={
        "code": "session_expired", "message": "Please log in again."})
    if not token:
        raise expired
    claims = tokens.decode_token(token)
    if not claims or claims.get("type") != "refresh":
        raise expired
    try:
        user_id = int(claims.get("sub"))
    except (TypeError, ValueError):
        raise expired

    user = _get_user(user_id)
    if not user or not user["is_active"]:
        raise expired
    if int(user["token_version"]) != int(claims.get("tv", -1)):
        raise expired

    _issue_session(response, user)
    return {"ok": True, "user": _user_public(user)}


# --- account / session info -----------------------------------------------

@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    with get_db() as db:
        rows = db.execute(
            "SELECT c.id, c.name, c.is_personal, c.owner_user_id, m.role "
            "FROM collections c JOIN collection_members m ON m.collection_id = c.id "
            "WHERE m.user_id = ? ORDER BY c.id",
            (user.id,),
        ).fetchall()
        mfa = db.execute(
            "SELECT mfa_enabled, mfa_required FROM users WHERE id = ?", (user.id,)
        ).fetchone()
    collections = [
        {"id": r["id"], "name": r["name"], "is_personal": bool(r["is_personal"]),
         "is_owner": r["owner_user_id"] == user.id, "role": r["role"]}
        for r in rows
    ]
    # Super admins are always required to use MFA; regular users only if flagged.
    mfa_required = bool(user.is_super_admin or (mfa and mfa["mfa_required"]))
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_super_admin": user.is_super_admin,
        "mfa_enabled": bool(mfa["mfa_enabled"]) if mfa else False,
        "mfa_required": mfa_required,
        "collections": collections,
    }


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest, response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    record = _get_user(user.id)
    if not verify_password(payload.current_password, record["password_hash"]):
        raise HTTPException(status_code=400, detail={
            "code": "invalid_password", "message": "Current password is incorrect."})
    with get_db() as db:
        # Bump token_version to revoke all other outstanding sessions.
        db.execute(
            "UPDATE users SET password_hash = ?, token_version = token_version + 1 WHERE id = ?",
            (hash_password(payload.new_password), user.id),
        )
        db.commit()
    # Re-issue this session so the current client stays logged in.
    _issue_session(response, _get_user(user.id))
    return {"ok": True}


# --- MFA (TOTP) ------------------------------------------------------------

@router.post("/mfa/setup")
async def mfa_setup(user: CurrentUser = Depends(get_current_user)):
    """Generate (but do not yet enable) a TOTP secret; return a QR to scan."""
    secret = totp.generate_secret()
    with get_db() as db:
        db.execute(
            "UPDATE users SET mfa_secret = ?, mfa_enabled = 0 WHERE id = ?", (secret, user.id)
        )
        db.commit()
    return {
        "secret": secret,
        "otpauth_uri": totp.provisioning_uri(secret, user.email),
        "qr": totp.qr_data_uri(secret, user.email),
    }


@router.post("/mfa/verify")
async def mfa_verify(payload: MfaVerifyRequest, user: CurrentUser = Depends(get_current_user)):
    """Confirm the user can produce a valid code, then enable MFA and return
    one-time recovery codes (shown once)."""
    record = _get_user(user.id)
    if not record["mfa_secret"]:
        raise HTTPException(status_code=400, detail={
            "code": "mfa_not_started", "message": "Start MFA setup first."})
    if not totp.verify_code(record["mfa_secret"], payload.code):
        raise HTTPException(status_code=400, detail={
            "code": "mfa_invalid", "message": "That code didn't match. Try again."})
    plaintext_codes, hashed = totp.generate_recovery_codes()
    with get_db() as db:
        db.execute(
            "UPDATE users SET mfa_enabled = 1, mfa_recovery_codes = ? WHERE id = ?",
            (hashed, user.id),
        )
        db.commit()
    return {"ok": True, "recovery_codes": plaintext_codes}


@router.post("/mfa/disable")
async def mfa_disable(payload: MfaDisableRequest, user: CurrentUser = Depends(get_current_user)):
    record = _get_user(user.id)
    if not verify_password(payload.password, record["password_hash"]):
        raise HTTPException(status_code=400, detail={
            "code": "invalid_password", "message": "Password is incorrect."})
    with get_db() as db:
        db.execute(
            "UPDATE users SET mfa_enabled = 0, mfa_secret = NULL, mfa_recovery_codes = NULL WHERE id = ?",
            (user.id,),
        )
        db.commit()
    return {"ok": True}
