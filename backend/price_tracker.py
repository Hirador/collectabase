import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from .auth.deps import (
    ActiveCollection, CurrentUser, active_collection, get_current_user,
    require_super_admin, require_write,
)
from .database import dict_from_row, get_db, set_app_meta
from . import jobs

from .services.price.utils import (
    PLATFORM_SLUGS, COMPLETENESS_TO_PC, _to_eur, get_eur_rate, _normalize_text
)
from .services.price.catalog import (
    _lookup_local_catalog_price, scrape_platform_catalog,
    _upsert_catalog_entries, _derive_platform_label
)
from .services.price.providers.ebay import fetch_ebay_market_price, _ebay_credentials
from .services.price.providers.rawg import fetch_rawg_reference, _rawg_key
from .services.price.providers.pricecharting import (
    _fetch_pricecharting_scrape, fetch_pricecharting
)

router = APIRouter()

logger = logging.getLogger("collectabase.price_tracker")


def _apply_prices_to_copies(db, game_id: int, prices_eur: dict) -> list:
    """Update each copy's current_value from PC tier prices based on completeness mapping."""
    copies = db.execute(
        "SELECT id, completeness FROM game_copies WHERE game_id = ?", (game_id,)
    ).fetchall()
    updated = []
    for copy in copies:
        completeness = (copy["completeness"] or "").strip()
        pc_key = COMPLETENESS_TO_PC.get(completeness, "loose")
        price = prices_eur.get(pc_key)
        if price is not None:
            db.execute(
                "UPDATE game_copies SET current_value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (price, copy["id"]),
            )
            updated.append({
                "copy_id": copy["id"],
                "completeness": completeness or "Loose",
                "pc_tier": pc_key,
                "current_value": price,
            })
    return updated

def _get_game_for_price_lookup(game_id: int, collection_id: int):
    with get_db() as db:
        row = db.execute(
            """
            SELECT g.*, p.name as platform_name
            FROM games g LEFT JOIN platforms p ON g.platform_id = p.id
            WHERE g.id = ? AND g.collection_id = ?
            """,
            (game_id, collection_id),
        ).fetchone()
    return dict_from_row(row) if row else None


def _game_in_collection(db, game_id: int, collection_id: int) -> bool:
    return db.execute(
        "SELECT 1 FROM games WHERE id = ? AND collection_id = ?", (game_id, collection_id)
    ).fetchone() is not None


@router.post("/api/games/{game_id}/fetch-market-price")
async def fetch_market_price(game_id: int, source: Optional[str] = None,
                             ac: ActiveCollection = Depends(active_collection)):
    """Primary source: PriceCharting scraper. Fallback: eBay Browse."""
    require_write(ac)
    game = _get_game_for_price_lookup(game_id, ac.id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    ebay_enabled = all(_ebay_credentials())
    rawg_enabled = _rawg_key() is not None

    item_type = game.get("item_type") or "game"
    is_pc_supported = item_type in ("game", "console", "controller", "accessory", "funko", "comic")

    if source == 'ebay':
        if not ebay_enabled:
            return {"error": "eBay is not configured in Settings."}
        ebay = await fetch_ebay_market_price(game["title"], game.get("platform_name") or "", item_type)
        if ebay:
            prices_eur = {"loose": ebay["market_price"]}
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO price_history
                        (game_id, source, loose_price, complete_price, new_price, eur_rate)
                    VALUES (?, 'ebay', ?, NULL, NULL, 1.0)
                    """,
                    (game_id, ebay["market_price"]),
                )
                copies_updated = _apply_prices_to_copies(db, game_id, prices_eur)
                db.commit()
            return {
                "market_price": ebay["market_price"],
                "source": "ebay",
                "sample_size": ebay["sample_size"],
                "price_min": ebay["price_min"],
                "price_max": ebay["price_max"],
                "copies_updated": copies_updated,
            }
        return {"error": "No eBay listings found for this game."}

    if is_pc_supported:
        catalog = _lookup_local_catalog_price(game["title"], game.get("platform_name") or "")
        if not catalog:
            # Retry without platform constraint for mismatched/legacy platform labels.
            catalog = _lookup_local_catalog_price(game["title"], "")
        if catalog:
            prices_eur = {
                "loose": catalog["loose_eur"],
                "complete": catalog["cib_eur"],
                "new": catalog["new_eur"],
                "graded": catalog.get("graded_eur"),
                "box_only": catalog.get("box_only_eur"),
                "manual_only": catalog.get("manual_only_eur"),
            }
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO price_history
                        (game_id, source, loose_price, complete_price, new_price,
                         graded_price, box_only_price, manual_only_price,
                         eur_rate, pricecharting_id)
                    VALUES (?, 'pricecharting', ?, ?, ?, ?, ?, ?, 1.0, ?)
                    """,
                    (
                        game_id,
                        prices_eur["loose"], prices_eur["complete"], prices_eur["new"],
                        prices_eur["graded"], prices_eur["box_only"], prices_eur["manual_only"],
                        catalog["pricecharting_id"] or None,
                    ),
                )
                copies_updated = _apply_prices_to_copies(db, game_id, prices_eur)
                db.commit()
            return {
                "market_price": prices_eur["loose"],
                "source": "pricecharting",
                "prices": prices_eur,
                "copies_updated": copies_updated,
                "matched_title": catalog["product_name"],
                "matched_platform": catalog["platform"],
                "match_score": catalog["match_score"],
            }

        eur_rate = await get_eur_rate()

        # Always try scraper first; token does not gate this path.
        pc = await _fetch_pricecharting_scrape(game["title"], game.get("platform_name") or "")
        if pc:
            prices_eur = {
                "loose": _to_eur(pc["loose_usd"], eur_rate),
                "complete": _to_eur(pc["cib_usd"], eur_rate),
                "new": _to_eur(pc["new_usd"], eur_rate),
                "graded": _to_eur(pc.get("graded_usd"), eur_rate),
                "box_only": _to_eur(pc.get("box_only_usd"), eur_rate),
                "manual_only": _to_eur(pc.get("manual_only_usd"), eur_rate),
            }
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO price_history
                        (game_id, source, loose_price, complete_price, new_price,
                         graded_price, box_only_price, manual_only_price,
                         eur_rate, pricecharting_id)
                    VALUES (?, 'pricecharting', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (game_id,
                     prices_eur["loose"], prices_eur["complete"], prices_eur["new"],
                     prices_eur["graded"], prices_eur["box_only"], prices_eur["manual_only"],
                     eur_rate, pc["pricecharting_id"]),
                )
                copies_updated = _apply_prices_to_copies(db, game_id, prices_eur)
                db.commit()
            return {
                "market_price": prices_eur["loose"],
                "source": "pricecharting",
                "prices": prices_eur,
                "copies_updated": copies_updated,
            }

    if ebay_enabled:
        ebay = await fetch_ebay_market_price(game["title"], game.get("platform_name") or "", item_type)
        if ebay:
            prices_eur = {"loose": ebay["market_price"]}
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO price_history
                        (game_id, source, loose_price, complete_price, new_price, eur_rate)
                    VALUES (?, 'ebay', ?, NULL, NULL, 1.0)
                    """,
                    (game_id, ebay["market_price"]),
                )
                copies_updated = _apply_prices_to_copies(db, game_id, prices_eur)
                db.commit()
            return {
                "market_price": ebay["market_price"],
                "source": "ebay",
                "sample_size": ebay["sample_size"],
                "price_min": ebay["price_min"],
                "price_max": ebay["price_max"],
                "copies_updated": copies_updated,
            }

    if rawg_enabled:
        rawg = await fetch_rawg_reference(game["title"], game.get("platform_name") or "")
        if rawg:
            return {
                "error": "No market price found. Set value manually.",
                "source": "rawg",
                "rawg_url": rawg.get("rawg_url"),
                "store_links": rawg.get("store_links", []),
            }

    return {"error": "No market price found. Set value manually."}


@router.post("/api/games/{game_id}/price-check")
async def check_price(game_id: int, ac: ActiveCollection = Depends(active_collection)):
    """Backward-compatible alias."""
    return await fetch_market_price(game_id, ac=ac)


@router.get("/api/games/{game_id}/price-history")
async def get_price_history(game_id: int, ac: ActiveCollection = Depends(active_collection)):
    """Return the last 20 price snapshots for a game."""
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise HTTPException(status_code=404, detail="Game not found")
        rows = db.execute(
            """
            SELECT * FROM price_history
            WHERE game_id = ?
            ORDER BY fetched_at DESC
            LIMIT 20
            """,
            (game_id,),
        ).fetchall()
        return [dict_from_row(r) for r in rows]


@router.delete("/api/games/{game_id}/price-history/{entry_id}")
async def delete_price_history_entry(game_id: int, entry_id: int,
                                     ac: ActiveCollection = Depends(active_collection)):
    """Delete any price history entry (manual or provider)."""
    require_write(ac)
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise HTTPException(status_code=404, detail="Game not found")
        row = db.execute(
            "SELECT id, game_id, source FROM price_history WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Price history entry not found")
        item = dict_from_row(row)
        if int(item["game_id"]) != int(game_id):
            raise HTTPException(status_code=404, detail="Price history entry not found for this game")
        db.execute("DELETE FROM price_history WHERE id = ?", (entry_id,))
        db.commit()
    return {"ok": True}


@router.post("/api/prices/update-all")
async def bulk_price_update(
    background_tasks: BackgroundTasks,
    limit: int = 100,
    ac: ActiveCollection = Depends(active_collection),
):
    """Kick off a background job to fetch prices for up to `limit` games in the
    active collection. Returns immediately with a job_id; poll /api/jobs/{job_id}.
    """
    require_write(ac)
    with get_db() as db:
        rows = db.execute(
            """
            SELECT g.id, g.title, g.item_type, p.name as platform_name
            FROM games g
            LEFT JOIN platforms p ON g.platform_id = p.id
            WHERE g.is_wishlist = 0 AND g.collection_id = ?
            ORDER BY g.id ASC
            LIMIT ?
            """,
            (ac.id, limit),
        ).fetchall()
        game_list = [dict_from_row(r) for r in rows]

    job_id = jobs.start("bulk_price_update", total=len(game_list))
    background_tasks.add_task(_run_bulk_price_update, job_id, game_list)
    return {"job_id": job_id, "total": len(game_list), "state": "running"}


async def _run_bulk_price_update(job_id: str, game_list: list) -> None:
    eur_rate = await get_eur_rate()
    success = 0
    failed = 0

    for i, game in enumerate(game_list):
        jobs.update(job_id, progress=i + 1)

        item_type = game.get("item_type") or "game"
        is_pc_supported = item_type in ("game", "console", "controller", "accessory", "funko", "comic")
        
        if not is_pc_supported:
            failed += 1
            await asyncio.sleep(0.01)
            continue

        catalog = _lookup_local_catalog_price(game["title"], game.get("platform_name") or "")
        if not catalog:
            catalog = _lookup_local_catalog_price(game["title"], "")

        if catalog:
            prices_eur = {
                "loose": catalog["loose_eur"],
                "complete": catalog["cib_eur"],
                "new": catalog["new_eur"],
                "graded": catalog.get("graded_eur"),
                "box_only": catalog.get("box_only_eur"),
                "manual_only": catalog.get("manual_only_eur"),
            }
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO price_history
                        (game_id, source, loose_price, complete_price, new_price,
                         graded_price, box_only_price, manual_only_price,
                         eur_rate, pricecharting_id)
                    VALUES (?, 'pricecharting', ?, ?, ?, ?, ?, ?, 1.0, ?)
                    """,
                    (
                        game["id"],
                        prices_eur["loose"], prices_eur["complete"], prices_eur["new"],
                        prices_eur["graded"], prices_eur["box_only"], prices_eur["manual_only"],
                        catalog["pricecharting_id"] or None,
                    ),
                )
                _apply_prices_to_copies(db, game["id"], prices_eur)
                db.commit()
            success += 1
            await asyncio.sleep(0.1)
            continue

        pc = await fetch_pricecharting(game["title"], game["platform_name"] or "")
        if pc:
            prices_eur = {
                "loose": _to_eur(pc["loose_usd"], eur_rate),
                "complete": _to_eur(pc["cib_usd"], eur_rate),
                "new": _to_eur(pc["new_usd"], eur_rate),
                "graded": _to_eur(pc.get("graded_usd"), eur_rate),
                "box_only": _to_eur(pc.get("box_only_usd"), eur_rate),
                "manual_only": _to_eur(pc.get("manual_only_usd"), eur_rate),
            }
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO price_history
                        (game_id, source, loose_price, complete_price, new_price,
                         graded_price, box_only_price, manual_only_price,
                         eur_rate, pricecharting_id)
                    VALUES (?, 'pricecharting', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        game["id"],
                        prices_eur["loose"], prices_eur["complete"], prices_eur["new"],
                        prices_eur["graded"], prices_eur["box_only"], prices_eur["manual_only"],
                        eur_rate, pc["pricecharting_id"],
                    ),
                )
                _apply_prices_to_copies(db, game["id"], prices_eur)
                db.commit()
            success += 1
        else:
            failed += 1

        await asyncio.sleep(0.4)  # stay polite to PriceCharting.

    finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    set_app_meta("last_bulk_price_update_at", finished_at)
    set_app_meta("last_bulk_price_update_success", str(success))
    set_app_meta("last_bulk_price_update_failed", str(failed))
    set_app_meta("last_bulk_price_update_total", str(len(game_list)))
    set_app_meta("last_bulk_price_update_error", "")
    jobs.finish(job_id, success=success, failed=failed)


@router.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, _user: CurrentUser = Depends(get_current_user)):
    """Poll the status of a background job."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/api/jobs")
async def list_active_jobs(_user: CurrentUser = Depends(get_current_user)):
    """Return all currently running background jobs."""
    return jobs.list_active()


class ManualPriceEntry(BaseModel):
    loose_price: Optional[float] = None
    complete_price: Optional[float] = None
    new_price: Optional[float] = None
    graded_price: Optional[float] = None
    box_only_price: Optional[float] = None
    manual_only_price: Optional[float] = None


class CatalogPriceApply(BaseModel):
    catalog_id: int


@router.post("/api/games/{game_id}/price-manual")
async def add_manual_price(game_id: int, entry: ManualPriceEntry,
                           ac: ActiveCollection = Depends(active_collection)):
    """Save a manually entered price snapshot (source='manual')."""
    require_write(ac)
    with get_db() as db:
        row = db.execute(
            "SELECT id FROM games WHERE id = ? AND collection_id = ?", (game_id, ac.id)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Game not found")

    with get_db() as db:
        db.execute(
            """
            INSERT INTO price_history
                (game_id, source, loose_price, complete_price, new_price,
                 graded_price, box_only_price, manual_only_price)
            VALUES (?, 'manual', ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                entry.loose_price, entry.complete_price, entry.new_price,
                entry.graded_price, entry.box_only_price, entry.manual_only_price,
            ),
        )
        db.commit()
    return {"ok": True}


class CopyValueUpdate(BaseModel):
    current_value: Optional[float] = None


@router.put("/api/games/{game_id}/copies/{copy_id}/current-value")
async def set_copy_current_value(game_id: int, copy_id: int, payload: CopyValueUpdate,
                                 ac: ActiveCollection = Depends(active_collection)):
    """Set the per-copy baseline value used for P/L calculation."""
    require_write(ac)
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise HTTPException(status_code=404, detail="Game not found")
        row = db.execute(
            "SELECT id FROM game_copies WHERE id = ? AND game_id = ?", (copy_id, game_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Copy not found")
        db.execute(
            "UPDATE game_copies SET current_value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload.current_value, copy_id),
        )
        db.commit()
    return {"ok": True, "copy_id": copy_id, "current_value": payload.current_value}


@router.post("/api/games/{game_id}/price-from-catalog")
async def apply_catalog_price(game_id: int, payload: CatalogPriceApply,
                              ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    with get_db() as db:
        game = db.execute(
            "SELECT id FROM games WHERE id = ? AND collection_id = ?", (game_id, ac.id)
        ).fetchone()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

        row = db.execute("SELECT * FROM price_catalog WHERE id = ?", (payload.catalog_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Catalog entry not found")
        item = dict_from_row(row)

        loose = item.get("loose_eur")
        cib = item.get("cib_eur")
        new = item.get("new_eur")
        if loose is None and cib is None and new is None:
            raise HTTPException(status_code=400, detail="Catalog entry has no usable prices")

        db.execute(
            """
            INSERT INTO price_history
                (game_id, source, loose_price, complete_price, new_price, eur_rate, pricecharting_id)
            VALUES (?, 'pricecharting', ?, ?, ?, 1.0, ?)
            """,
            (game_id, loose, cib, new, item.get("pricecharting_id") or None),
        )

        if loose is not None:
            db.execute(
                "UPDATE games SET current_value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (loose, game_id),
            )

        db.commit()

    return {
        "ok": True,
        "market_price": loose,
        "source": "pricecharting",
        "matched_title": item.get("title"),
        "matched_platform": item.get("platform"),
    }


@router.post("/api/price-catalog/scrape")
async def scrape_catalog(
    platform: str = "all",
    q: Optional[str] = None,
    _admin: CurrentUser = Depends(require_super_admin),
):
    """Scrape PriceCharting catalog for one or all platforms into price_catalog table."""
    query = (q or "").strip()
    if query:
        platform_hint = None
        if platform and platform != "all":
            platform_hint = next(
                (lbl for lbl, slug in PLATFORM_SLUGS.items() if slug == platform or lbl == platform),
                None,
            )
            if not platform_hint:
                raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

        scraped = await _fetch_pricecharting_scrape(query, platform_hint or "")
        if not scraped:
            return {
                "scraped": 0,
                "inserted": 0,
                "updated": 0,
                "unchanged": 0,
                "deduped_in_batch": 0,
                "duplicates_removed": 0,
                "platforms": [platform_hint] if platform_hint else [],
                "query": query,
                "targeted": True,
                "error": "No PriceCharting result found for query",
            }

        eur_rate = await get_eur_rate()
        resolved_platform = platform_hint or _derive_platform_label(scraped.get("page_url")) or "Unknown"
        entry = {
            "pricecharting_id": scraped.get("pricecharting_id") or "",
            "title": scraped.get("product_name") or query,
            "platform": resolved_platform,
            "loose_usd": scraped.get("loose_usd"),
            "cib_usd": scraped.get("cib_usd"),
            "new_usd": scraped.get("new_usd"),
            "page_url": scraped.get("page_url") or "",
        }
        stats = _upsert_catalog_entries([entry], eur_rate)
        result = {
            "scraped": stats["processed"],
            "inserted": stats["inserted"],
            "updated": stats["updated"],
            "unchanged": stats["unchanged"],
            "deduped_in_batch": stats["deduped_in_batch"],
            "duplicates_removed": stats["duplicates_removed"],
            "platforms": [resolved_platform],
            "query": query,
            "targeted": True,
        }
        finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        set_app_meta("last_catalog_scrape_at", finished_at)
        set_app_meta("last_catalog_scrape_platforms", ", ".join(result["platforms"]))
        set_app_meta("last_catalog_scrape_total", result["scraped"])
        return result

    if platform == "all":
        targets = list(PLATFORM_SLUGS.items())
    else:
        # Accept either a slug (e.g. "nintendo-switch") or a label
        label = next(
            (lbl for lbl, slug in PLATFORM_SLUGS.items() if slug == platform or lbl == platform),
            None,
        )
        if not label:
            raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
        targets = [(label, PLATFORM_SLUGS[label])]

    eur_rate = await get_eur_rate()
    total_scraped = 0
    total_inserted = 0
    total_updated = 0
    total_unchanged = 0
    total_deduped_in_batch = 0
    total_duplicates_removed = 0

    for label, slug in targets:
        print(f"Starting catalog scrape for {label} ({slug})")
        entries = await scrape_platform_catalog(slug, label)
        stats = _upsert_catalog_entries(entries, eur_rate)
        total_scraped += stats["processed"]
        total_inserted += stats["inserted"]
        total_updated += stats["updated"]
        total_unchanged += stats["unchanged"]
        total_deduped_in_batch += stats["deduped_in_batch"]
        total_duplicates_removed += stats["duplicates_removed"]
        print(
            f"Finished {label}: processed={stats['processed']} inserted={stats['inserted']} "
            f"updated={stats['updated']} unchanged={stats['unchanged']}"
        )
        if len(targets) > 1:
            await asyncio.sleep(2.0)  # pause between platforms when scraping all

    result = {
        "scraped": total_scraped,
        "inserted": total_inserted,
        "updated": total_updated,
        "unchanged": total_unchanged,
        "deduped_in_batch": total_deduped_in_batch,
        "duplicates_removed": total_duplicates_removed,
        "platforms": [lbl for lbl, _ in targets],
    }
    finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    set_app_meta("last_catalog_scrape_at", finished_at)
    set_app_meta("last_catalog_scrape_platforms", ", ".join(result["platforms"]))
    set_app_meta("last_catalog_scrape_total", result["scraped"])
    return result


@router.post("/api/price-catalog/enrich-library")
async def enrich_catalog_from_library(limit: int = 120,
                                      ac: ActiveCollection = Depends(active_collection)):
    """
    Fill price_catalog incrementally by scraping titles present in the active
    collection's library. Grows coverage beyond the paginated console scrape.
    """
    require_write(ac)
    with get_db() as db:
        rows = db.execute(
            """
            SELECT g.id, g.title, p.name as platform_name
            FROM games g
            LEFT JOIN platforms p ON g.platform_id = p.id
            WHERE g.is_wishlist = 0 AND g.collection_id = ?
            ORDER BY g.updated_at DESC, g.id DESC
            LIMIT ?
            """,
            (ac.id, limit),
        ).fetchall()

    games = [dict_from_row(r) for r in rows]
    scanned = len(games)
    skipped_existing = 0
    failed = 0
    fetched_entries = []

    for game in games:
        title = (game.get("title") or "").strip()
        platform_name = (game.get("platform_name") or "").strip()
        if not title:
            continue

        existing = _lookup_local_catalog_price(title, platform_name)
        if not existing:
            existing = _lookup_local_catalog_price(title, "")
        if existing and float(existing.get("match_score") or 0) >= 0.9:
            skipped_existing += 1
            continue

        scraped = await _fetch_pricecharting_scrape(title, platform_name)
        if not scraped:
            failed += 1
            await asyncio.sleep(0.35)
            continue

        resolved_platform = (
            _derive_platform_label(scraped.get("page_url"))
            or _normalize_text(platform_name)
            or "unknown"
        )
        fetched_entries.append(
            {
                "pricecharting_id": scraped.get("pricecharting_id") or "",
                "title": scraped.get("product_name") or title,
                "platform": resolved_platform,
                "loose_usd": scraped.get("loose_usd"),
                "cib_usd": scraped.get("cib_usd"),
                "new_usd": scraped.get("new_usd"),
                "page_url": scraped.get("page_url") or "",
            }
        )
        await asyncio.sleep(0.5)

    eur_rate = await get_eur_rate()
    stats = _upsert_catalog_entries(fetched_entries, eur_rate)

    finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    set_app_meta("last_catalog_scrape_at", finished_at)
    set_app_meta("last_catalog_scrape_platforms", "library-enrich")
    set_app_meta("last_catalog_scrape_total", stats["processed"])
    set_app_meta("last_catalog_enrich_scanned", scanned)
    set_app_meta("last_catalog_enrich_skipped_existing", skipped_existing)
    set_app_meta("last_catalog_enrich_failed", failed)

    return {
        "library": True,
        "scanned": scanned,
        "skipped_existing": skipped_existing,
        "failed": failed,
        "fetched": len(fetched_entries),
        "scraped": stats["processed"],
        "inserted": stats["inserted"],
        "updated": stats["updated"],
        "unchanged": stats["unchanged"],
        "deduped_in_batch": stats["deduped_in_batch"],
        "duplicates_removed": stats["duplicates_removed"],
    }


@router.get("/api/price-catalog")
async def search_catalog(
    search: Optional[str] = None,
    platform: Optional[str] = None,
    sort: str = "title",
    order: str = "asc",
    page: int = 1,
    limit: int = 50,
    _user: CurrentUser = Depends(get_current_user),
):
    """Search and paginate the local price catalog."""
    allowed_sorts = {"title", "platform", "loose_eur", "cib_eur", "new_eur"}
    if sort not in allowed_sorts:
        sort = "title"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"

    conditions = []
    params = []

    if search:
        conditions.append("title LIKE ?")
        params.append(f"%{search}%")
    if platform:
        conditions.append("platform = ?")
        params.append(platform)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * limit

    with get_db() as db:
        count_row = db.execute(
            f"SELECT COUNT(*) as count FROM price_catalog {where}", tuple(params)
        ).fetchone()
        total = count_row["count"] if count_row else 0

        rows = db.execute(
            f"""
            SELECT * FROM price_catalog
            {where}
            ORDER BY {sort} {order_dir}
            LIMIT ? OFFSET ?
            """,
            tuple(params + [limit, offset]),
        ).fetchall()

    return {
        "items": [dict_from_row(r) for r in rows],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/api/price-catalog/platforms")
async def catalog_platforms(_user: CurrentUser = Depends(get_current_user)):
    """Return distinct platforms present in the price catalog."""
    with get_db() as db:
        rows = db.execute(
            "SELECT DISTINCT platform FROM price_catalog ORDER BY platform"
        ).fetchall()
    return [r["platform"] for r in rows]


@router.delete("/api/price-catalog")
async def clear_catalog(platform: Optional[str] = None,
                        _admin: CurrentUser = Depends(require_super_admin)):
    """Delete all (or one platform's) entries from the price catalog."""
    with get_db() as db:
        if platform:
            db.execute("DELETE FROM price_catalog WHERE platform = ?", (platform,))
        else:
            db.execute("DELETE FROM price_catalog")
        db.commit()
    return {"ok": True}
