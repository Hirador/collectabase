import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .version import APP_VERSION

# Load env before importing local modules that read os.getenv at import time.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "backend" / ".env")

from .api.routes.catalog import router as catalog_router
from .api.routes.games import router as games_router
from .api.routes.import_export import UPLOADS_DIR, router as import_export_router
from .api.routes.auth import router as auth_router
from .api.routes.collections import router as collections_router
from .api.routes.lookup import router as lookup_router
from .api.routes.lots import router as lots_router
from .api.routes.users import router as users_router
from .api.routes.settings import router as settings_router
from .api.routes.stats import router as stats_router
from .clz_import import router as clz_router
from .database import init_db
from .price_tracker import router as price_router
from .scheduler import init_scheduler, shutdown_scheduler


app = FastAPI(title="Collectabase", version=APP_VERSION)
_startup_time = time.time()
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(collections_router)
app.include_router(games_router)
app.include_router(lookup_router)
app.include_router(catalog_router)
app.include_router(lots_router)
app.include_router(import_export_router)
app.include_router(stats_router)
app.include_router(settings_router)
app.include_router(clz_router)
app.include_router(price_router)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend", "dist")
FRONTEND_DIR_RESOLVED = Path(FRONTEND_DIR).resolve()
CONSOLE_FALLBACKS_DIR = os.path.join(BASE_DIR, "backend", "static", "console-fallbacks")

assets_dir = os.path.join(FRONTEND_DIR, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

if os.path.isdir(CONSOLE_FALLBACKS_DIR):
    app.mount("/console-fallbacks", StaticFiles(directory=CONSOLE_FALLBACKS_DIR), name="console-fallbacks")

os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


def _backfill_personal_collections():
    """Ensure every active user has at least one collection to work in.

    Users created before the auto-personal-collection change (or any user who
    somehow ends up with no membership) would otherwise have no scope to add
    items and a hidden collection switcher. Idempotent: only touches users with
    zero memberships. Build inserts from values read up-front (never SELECT
    after commit — the legacy DB wrapper caches its connection)."""
    from .database import get_db

    with get_db() as db:
        orphans = db.execute(
            "SELECT u.id, u.email, u.display_name FROM users u "
            "WHERE u.is_active = 1 "
            "AND NOT EXISTS (SELECT 1 FROM collection_members m WHERE m.user_id = u.id)"
        ).fetchall()
        for u in orphans:
            label = (u["display_name"] or "").strip() or u["email"].split("@")[0]
            col = db.execute(
                "INSERT INTO collections (name, owner_user_id, is_personal) VALUES (?, ?, 1)",
                (f"{label}'s Collection", u["id"]),
            )
            db.execute(
                "INSERT INTO collection_members (collection_id, user_id, role) VALUES (?, ?, 'owner')",
                (col.lastrowid, u["id"]),
            )
        if orphans:
            db.commit()


@app.on_event("startup")
async def startup_event():
    init_db()
    _backfill_personal_collections()
    init_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    shutdown_scheduler()


@app.get("/api/health")
async def health_check():
    """Health check for Docker / Portainer / monitoring."""
    from .database import get_db
    db_ok = False
    try:
        with get_db() as db:
            db.execute("SELECT 1").fetchone()
            db_ok = True
    except Exception:
        pass
    uptime = int(time.time() - _startup_time)
    return {
        "status": "healthy" if db_ok else "degraded",
        "version": APP_VERSION,
        "database": "ok" if db_ok else "error",
        "uptime_seconds": uptime,
    }


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR_RESOLVED / "index.html"))


@app.get("/{path:path}")
async def catch_all(path: str):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "API endpoint not found"})

    requested = (FRONTEND_DIR_RESOLVED / path).resolve()
    try:
        requested.relative_to(FRONTEND_DIR_RESOLVED)
    except ValueError:
        return FileResponse(str(FRONTEND_DIR_RESOLVED / "index.html"))

    if requested.exists() and requested.is_file():
        return FileResponse(str(requested))
    return FileResponse(str(FRONTEND_DIR_RESOLVED / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
