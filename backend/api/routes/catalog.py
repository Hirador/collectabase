"""
Disc/cartridge catalog API: one-click update from Redump/No-Intro DAT files and
serial/name lookup that feeds the Add Game flow.
"""
from fastapi import APIRouter, BackgroundTasks, Depends

from ..schemas import CatalogSearch, EditionLookup
from ..security import require_admin_access
from ... import jobs
from ...database import get_db
from ...services.catalog import catalog_db
from ...services.catalog.dat_import import update_catalog
from ...services.catalog.systems import all_systems
from ...services.lookup_service import lookup_igdb_editions


def _collection_editions() -> list[str]:
    """Distinct editions the user has already entered, so they reuse consistent
    names across their own collection."""
    try:
        with get_db() as db:
            rows = db.execute(
                "SELECT DISTINCT edition FROM games "
                "WHERE edition IS NOT NULL AND TRIM(edition) != '' ORDER BY edition"
            ).fetchall()
        return [r["edition"] for r in rows]
    except Exception:
        return []

router = APIRouter()

# Fallback editions offered even when neither IGDB nor the catalog list any.
_COMMON_EDITIONS = [
    "Collector's Edition", "Limited Edition", "Game of the Year Edition",
    "Deluxe Edition", "Special Edition", "Steelbook Edition", "Day One Edition",
    "Greatest Hits", "Platinum",
]


def _run_catalog_update(job_id: str, force: bool) -> None:
    def progress(done: int, total: int, system) -> None:
        jobs.update(job_id, progress=done, total=total)

    try:
        summary = update_catalog(force=force, progress_cb=progress)
        jobs.finish(job_id, success=summary["updated"], failed=summary["errors"])
    except Exception as exc:  # noqa: BLE001
        jobs.fail(job_id, message=str(exc)[:300])


@router.post("/api/catalog/update")
async def catalog_update(
    background_tasks: BackgroundTasks,
    force: bool = False,
    _admin: None = Depends(require_admin_access),
):
    """Kick off a background catalog import. Poll /api/jobs/{job_id} for progress.

    Unchanged systems are skipped automatically (header-version / ETag compare);
    pass ``force=true`` to re-import everything.
    """
    total = len(all_systems())
    job_id = jobs.start("catalog_update", total=total)
    background_tasks.add_task(_run_catalog_update, job_id, force)
    return {"job_id": job_id, "total": total, "state": "running"}


@router.get("/api/catalog/status")
async def catalog_status():
    """Catalog size, per-system breakdown, and when it was last updated."""
    catalog_db.init_catalog_db()
    stats = catalog_db.get_stats()
    meta = catalog_db.meta_get_many(
        [
            "catalog_last_update_at",
            "catalog_last_update_updated",
            "catalog_last_update_errors",
        ]
    )
    return {
        "total_entries": stats["total_entries"],
        "systems": stats["systems"],
        "available_systems": len(all_systems()),
        "last_update_at": meta.get("catalog_last_update_at"),
        "last_update_updated": meta.get("catalog_last_update_updated"),
        "last_update_errors": meta.get("catalog_last_update_errors"),
    }


@router.post("/api/lookup/editions")
async def lookup_editions(payload: EditionLookup):
    """Edition options for the Add Game dropdown: 'Standard' first, then IGDB
    editions (Collector's/GOTY/...), then catalog edition tags (Platinum/Greatest
    Hits), then common presets. De-duplicated, case-insensitive."""
    editions: list[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        label = (label or "").strip()
        key = label.lower()
        if label and key not in seen:
            seen.add(key)
            editions.append(label)

    # The user's own editions first (consistency), then IGDB, catalog, presets.
    for e in _collection_editions():
        add(e)
    if payload.igdb_id:
        igdb = await lookup_igdb_editions(payload.igdb_id)
        for e in igdb.get("editions", []):
            add(e)
    if payload.title:
        catalog_db.init_catalog_db()
        for e in catalog_db.distinct_editions(payload.title):
            add(e)
    for e in _COMMON_EDITIONS:
        add(e)
    return {"editions": editions}


@router.post("/api/lookup/catalog")
async def lookup_catalog(search: CatalogSearch):
    """Search the catalog by serial (e.g. SLUS-00663) or by title."""
    catalog_db.init_catalog_db()
    results = catalog_db.search(
        search.query,
        limit=search.limit or 25,
        source=search.source,
        platform_name=search.platform_name,
        serial_only=bool(search.serial_only),
    )
    return {"query": search.query, "count": len(results), "results": results}
