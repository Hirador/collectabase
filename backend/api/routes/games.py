import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends

from ..errors import conflict, not_found
from ..schemas import CopyCreate, CopyUpdate, GameCreate, GameUpdate, PlatformCreate
from ...database import dict_from_row, get_db
from ...auth.deps import (
    ActiveCollection, CurrentUser, active_collection, get_current_user, require_write,
)
from ...services.lookup_service import cache_remote_cover

router = APIRouter()


def _game_in_collection(db, game_id: int, collection_id: int) -> bool:
    """True if the game exists and belongs to the active collection. Used to
    gate game-scoped sub-resources (copies, images) so they can't be reached
    cross-collection by guessing ids."""
    row = db.execute(
        "SELECT 1 FROM games WHERE id = ? AND collection_id = ?", (game_id, collection_id)
    ).fetchone()
    return row is not None


@router.get("/api/games")
async def list_games(
    platform: Optional[int] = None,
    wishlist: Optional[bool] = None,
    search: Optional[str] = None,
    ac: ActiveCollection = Depends(active_collection),
):
    with get_db() as db:
        query = """
            SELECT g.*, p.name as platform_name,
              (SELECT COUNT(*) FROM game_copies gc WHERE gc.game_id = g.id) as copies_count,
              (SELECT SUM(gc.current_value) FROM game_copies gc WHERE gc.game_id = g.id AND gc.current_value IS NOT NULL) as copies_total_value
            FROM games g
            LEFT JOIN platforms p ON g.platform_id = p.id
            WHERE g.collection_id = ?
        """
        params = [ac.id]

        if platform:
            query += " AND g.platform_id = ?"
            params.append(platform)
        if wishlist is not None:
            query += " AND g.is_wishlist = ?"
            params.append(1 if wishlist else 0)
        if search:
            query += " AND (g.title LIKE ? OR g.publisher LIKE ? OR g.developer LIKE ? OR COALESCE(p.name, '') LIKE ? OR COALESCE(g.item_type, '') LIKE ? OR COALESCE(g.barcode, '') LIKE ?)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param, search_param, search_param])

        query += " ORDER BY g.updated_at DESC"
        if search:
            query += " LIMIT 20"
        cursor = db.execute(query, tuple(params))
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.post("/api/games")
async def create_game(game: GameCreate, force: bool = False,
                      ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    if not force:
        with get_db() as db:
            existing = db.execute(
                "SELECT id FROM games WHERE LOWER(title) = LOWER(?) AND platform_id = ? AND collection_id = ?",
                (game.title, game.platform_id, ac.id),
            ).fetchone()
            if existing:
                raise conflict("Game already exists", {"existing_id": existing[0]})

    # Cache remote cover image locally before saving
    cover_url = await cache_remote_cover(game.cover_url)

    with get_db() as db:
        cursor = db.execute(
            '''
            INSERT INTO games (
                collection_id,
                title, platform_id, item_type, quantity, barcode, igdb_id, comicvine_id, hobbydb_id, mfc_id, release_date,
                publisher, developer, genre, description, cover_url,
                region, serial, disc_revision, languages, edition, catalog_source,
                condition, completeness, location,
                purchase_date, purchase_price, current_value, notes,
                is_wishlist, wishlist_max_price,
                character_name, series_name, scale, funko_number, vinyl_format
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                ac.id,
                game.title,
                game.platform_id,
                game.item_type,
                game.quantity,
                game.barcode,
                game.igdb_id,
                game.comicvine_id,
                game.hobbydb_id,
                game.mfc_id,
                game.release_date,
                game.publisher,
                game.developer,
                game.genre,
                game.description,
                cover_url,
                game.region,
                game.serial,
                game.disc_revision,
                game.languages,
                game.edition,
                game.catalog_source,
                game.condition,
                game.completeness,
                game.location,
                game.purchase_date,
                game.purchase_price,
                game.current_value,
                game.notes,
                1 if game.is_wishlist else 0,
                game.wishlist_max_price,
                game.character_name,
                game.series_name,
                game.scale,
                game.funko_number,
                game.vinyl_format,
            ),
        )
        game_id = cursor.lastrowid
        db.execute(
            """INSERT INTO game_copies
                   (game_id, condition, completeness, purchase_price, purchase_date, location, current_value, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                game_id,
                game.condition,
                game.completeness,
                game.purchase_price,
                game.purchase_date,
                game.location,
                game.current_value,
                game.notes,
            ),
        )
        db.commit()
        return {"id": game_id, "message": "Game created successfully"}


@router.get("/api/games/{game_id}")
async def get_game(game_id: int, ac: ActiveCollection = Depends(active_collection)):
    with get_db() as db:
        cursor = db.execute(
            """
            SELECT g.*, p.name as platform_name
            FROM games g
            LEFT JOIN platforms p ON g.platform_id = p.id
            WHERE g.id = ? AND g.collection_id = ?
            """,
            (game_id, ac.id),
        )
        game = dict_from_row(cursor.fetchone())
        if not game:
            raise not_found("Game not found")
        copies_cursor = db.execute(
            "SELECT * FROM game_copies WHERE game_id = ? ORDER BY id",
            (game_id,),
        )
        game["copies"] = [dict_from_row(row) for row in copies_cursor.fetchall()]
        return game


@router.put("/api/games/{game_id}")
async def update_game(game_id: int, game: GameUpdate,
                      ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM games WHERE id = ? AND collection_id = ?", (game_id, ac.id)
        ).fetchone()
        if not existing:
            raise not_found("Game not found")

        existing_data = dict_from_row(existing)

        # Cache remote cover image locally if it changed
        new_cover = game.cover_url if game.cover_url is not None else existing_data["cover_url"]
        if new_cover and new_cover != existing_data.get("cover_url"):
            new_cover = await cache_remote_cover(new_cover)

        merged = {
            "title": game.title or existing_data["title"],
            "platform_id": game.platform_id if game.platform_id is not None else existing_data["platform_id"],
            "item_type": game.item_type or existing_data["item_type"],
            "quantity": game.quantity if game.quantity is not None else existing_data["quantity"],
            "barcode": game.barcode if game.barcode is not None else existing_data["barcode"],
            "igdb_id": game.igdb_id if game.igdb_id is not None else existing_data["igdb_id"],
            "comicvine_id": game.comicvine_id if game.comicvine_id is not None else existing_data["comicvine_id"],
            "hobbydb_id": game.hobbydb_id if game.hobbydb_id is not None else existing_data["hobbydb_id"],
            "mfc_id": game.mfc_id if game.mfc_id is not None else existing_data["mfc_id"],
            "release_date": game.release_date if game.release_date is not None else existing_data["release_date"],
            "publisher": game.publisher if game.publisher is not None else existing_data["publisher"],
            "developer": game.developer if game.developer is not None else existing_data["developer"],
            "genre": game.genre if game.genre is not None else existing_data["genre"],
            "description": game.description if game.description is not None else existing_data["description"],
            "cover_url": new_cover if new_cover is not None else existing_data["cover_url"],
            "region": game.region if game.region is not None else existing_data["region"],
            "serial": game.serial if game.serial is not None else existing_data.get("serial"),
            "disc_revision": game.disc_revision if game.disc_revision is not None else existing_data.get("disc_revision"),
            "languages": game.languages if game.languages is not None else existing_data.get("languages"),
            "edition": game.edition if game.edition is not None else existing_data.get("edition"),
            "catalog_source": game.catalog_source if game.catalog_source is not None else existing_data.get("catalog_source"),
            "condition": game.condition if game.condition is not None else existing_data["condition"],
            "completeness": game.completeness if game.completeness is not None else existing_data["completeness"],
            "location": game.location if game.location is not None else existing_data["location"],
            "purchase_date": game.purchase_date if game.purchase_date is not None else existing_data["purchase_date"],
            "purchase_price": game.purchase_price if game.purchase_price is not None else existing_data["purchase_price"],
            "current_value": game.current_value if game.current_value is not None else existing_data["current_value"],
            "notes": game.notes if game.notes is not None else existing_data["notes"],
            "is_wishlist": (
                game.is_wishlist if game.is_wishlist is not None else bool(existing_data["is_wishlist"])
            ),
            "wishlist_max_price": (
                game.wishlist_max_price
                if game.wishlist_max_price is not None
                else existing_data["wishlist_max_price"]
            ),
            "character_name": game.character_name if game.character_name is not None else existing_data.get("character_name"),
            "series_name": game.series_name if game.series_name is not None else existing_data.get("series_name"),
            "scale": game.scale if game.scale is not None else existing_data.get("scale"),
            "funko_number": game.funko_number if game.funko_number is not None else existing_data.get("funko_number"),
            "vinyl_format": game.vinyl_format if game.vinyl_format is not None else existing_data.get("vinyl_format"),
        }

        db.execute(
            """
            UPDATE games SET
                title = ?, platform_id = ?, item_type = ?, quantity = ?, barcode = ?, igdb_id = ?, comicvine_id = ?, hobbydb_id = ?, mfc_id = ?, release_date = ?,
                publisher = ?, developer = ?, genre = ?, description = ?, cover_url = ?,
                region = ?, serial = ?, disc_revision = ?, languages = ?, edition = ?, catalog_source = ?,
                condition = ?, completeness = ?, location = ?,
                purchase_date = ?, purchase_price = ?, current_value = ?, notes = ?,
                is_wishlist = ?, wishlist_max_price = ?,
                character_name = ?, series_name = ?, scale = ?, funko_number = ?, vinyl_format = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                merged["title"],
                merged["platform_id"],
                merged["item_type"],
                merged["quantity"],
                merged["barcode"],
                merged["igdb_id"],
                merged["comicvine_id"],
                merged["hobbydb_id"],
                merged["mfc_id"],
                merged["release_date"],
                merged["publisher"],
                merged["developer"],
                merged["genre"],
                merged["description"],
                merged["cover_url"],
                merged["region"],
                merged["serial"],
                merged["disc_revision"],
                merged["languages"],
                merged["edition"],
                merged["catalog_source"],
                merged["condition"],
                merged["completeness"],
                merged["location"],
                merged["purchase_date"],
                merged["purchase_price"],
                merged["current_value"],
                merged["notes"],
                1 if merged["is_wishlist"] else 0,
                merged["wishlist_max_price"],
                merged["character_name"],
                merged["series_name"],
                merged["scale"],
                merged["funko_number"],
                merged["vinyl_format"],
                game_id,
            ),
        )
        first_copy = db.execute(
            "SELECT id FROM game_copies WHERE game_id = ? ORDER BY id LIMIT 1",
            (game_id,),
        ).fetchone()
        if first_copy:
            db.execute(
                """UPDATE game_copies SET
                       condition = ?, completeness = ?,
                       purchase_price = ?, purchase_date = ?, location = ?, notes = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (
                    merged["condition"],
                    merged["completeness"],
                    merged["purchase_price"],
                    merged["purchase_date"],
                    merged["location"],
                    merged["notes"],
                    first_copy[0],
                ),
            )
        db.commit()
        return {"id": game_id, "message": "Game updated successfully"}


@router.delete("/api/games/{game_id}")
async def delete_game(game_id: int, ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM games WHERE id = ? AND collection_id = ?", (game_id, ac.id)
        ).fetchone()
        if not existing:
            raise not_found("Game not found")
        db.execute("DELETE FROM games WHERE id = ?", (game_id,))
        db.commit()
        return {"message": "Game deleted successfully"}


@router.get("/api/games/{game_id}/images")
async def get_game_images(game_id: int, ac: ActiveCollection = Depends(active_collection)):
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise not_found("Game not found")
        cursor = db.execute(
            "SELECT id, image_url, is_primary, sort_order FROM item_images WHERE game_id = ? ORDER BY sort_order ASC, id ASC",
            (game_id,)
        )
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.post("/api/games/{game_id}/images")
async def add_game_image(game_id: int, payload: dict,
                         ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    url = payload.get("image_url")
    if not url:
        raise conflict("image_url is required")

    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise not_found("Game not found")

        # if it's the first image, make it primary
        count = db.execute("SELECT COUNT(*) FROM item_images WHERE game_id = ?", (game_id,)).fetchone()[0]
        is_primary = 1 if count == 0 else 0

        cursor = db.execute(
            "INSERT INTO item_images (game_id, image_url, is_primary, sort_order) VALUES (?, ?, ?, ?)",
            (game_id, url, is_primary, count)
        )
        new_id = cursor.lastrowid
        
        if is_primary:
            db.execute("UPDATE games SET cover_url = ? WHERE id = ?", (url, game_id))
            
        db.commit()
        return {"id": new_id, "image_url": url, "is_primary": bool(is_primary)}


@router.post("/api/games/{game_id}/images/{image_id}/primary")
async def set_primary_image(game_id: int, image_id: int,
                            ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise not_found("Game not found")
        img = db.execute("SELECT image_url FROM item_images WHERE id = ? AND game_id = ?", (image_id, game_id)).fetchone()
        if not img:
            raise not_found("Image not found")

        db.execute("UPDATE item_images SET is_primary = 0 WHERE game_id = ?", (game_id,))
        db.execute("UPDATE item_images SET is_primary = 1 WHERE id = ?", (image_id,))
        db.execute("UPDATE games SET cover_url = ? WHERE id = ?", (img[0], game_id))
        db.commit()
        return {"message": "Primary image updated"}


@router.delete("/api/games/{game_id}/images/{image_id}")
async def delete_game_image(game_id: int, image_id: int,
                            ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise not_found("Game not found")
        img = db.execute("SELECT is_primary FROM item_images WHERE id = ? AND game_id = ?", (image_id, game_id)).fetchone()
        if not img:
            raise not_found("Image not found")
        
        db.execute("DELETE FROM item_images WHERE id = ?", (image_id,))
        
        if img[0]:
            # If deleted primary, pick another one
            next_img = db.execute("SELECT id, image_url FROM item_images WHERE game_id = ? ORDER BY sort_order ASC, id ASC LIMIT 1", (game_id,)).fetchone()
            if next_img:
                db.execute("UPDATE item_images SET is_primary = 1 WHERE id = ?", (next_img[0],))
                db.execute("UPDATE games SET cover_url = ? WHERE id = ?", (next_img[1], game_id))
            else:
                db.execute("UPDATE games SET cover_url = NULL WHERE id = ?", (game_id,))
                
        db.commit()
        return {"message": "Image deleted"}


@router.get("/api/games/{game_id}/copies")
async def list_copies(game_id: int, ac: ActiveCollection = Depends(active_collection)):
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise not_found("Game not found")
        cursor = db.execute(
            "SELECT * FROM game_copies WHERE game_id = ? ORDER BY id",
            (game_id,),
        )
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.post("/api/games/{game_id}/copies")
async def add_copy(game_id: int, copy: CopyCreate,
                   ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise not_found("Game not found")
        cursor = db.execute(
            """INSERT INTO game_copies
                   (game_id, condition, completeness, purchase_price, purchase_date, location, current_value, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                game_id,
                copy.condition,
                copy.completeness,
                copy.purchase_price,
                copy.purchase_date,
                copy.location,
                copy.current_value,
                copy.notes,
            ),
        )
        new_id = cursor.lastrowid
        db.commit()
        return {
            "id": new_id,
            "game_id": game_id,
            "condition": copy.condition,
            "completeness": copy.completeness,
            "purchase_price": copy.purchase_price,
            "purchase_date": copy.purchase_date,
            "location": copy.location,
            "current_value": copy.current_value,
            "notes": copy.notes,
        }


@router.put("/api/games/{game_id}/copies/{copy_id}")
async def update_copy(game_id: int, copy_id: int, copy: CopyUpdate,
                      ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise not_found("Game not found")
        existing = db.execute(
            "SELECT * FROM game_copies WHERE id = ? AND game_id = ?", (copy_id, game_id)
        ).fetchone()
        if not existing:
            raise not_found("Copy not found")
        existing_data = dict_from_row(existing)
        merged = {
            "condition": copy.condition if copy.condition is not None else existing_data["condition"],
            "completeness": copy.completeness if copy.completeness is not None else existing_data["completeness"],
            "purchase_price": copy.purchase_price if copy.purchase_price is not None else existing_data["purchase_price"],
            "purchase_date": copy.purchase_date if copy.purchase_date is not None else existing_data["purchase_date"],
            "location": copy.location if copy.location is not None else existing_data["location"],
            "current_value": copy.current_value if copy.current_value is not None else existing_data.get("current_value"),
            "notes": copy.notes if copy.notes is not None else existing_data["notes"],
        }
        db.execute(
            """UPDATE game_copies SET
                   condition = ?, completeness = ?,
                   purchase_price = ?, purchase_date = ?, location = ?, current_value = ?, notes = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                merged["condition"], merged["completeness"],
                merged["purchase_price"], merged["purchase_date"], merged["location"],
                merged["current_value"], merged["notes"],
                copy_id,
            ),
        )
        db.commit()
        return {
            "id": copy_id,
            "game_id": game_id,
            "condition": merged["condition"],
            "completeness": merged["completeness"],
            "purchase_price": merged["purchase_price"],
            "purchase_date": merged["purchase_date"],
            "location": merged["location"],
            "current_value": merged["current_value"],
            "notes": merged["notes"],
        }


@router.delete("/api/games/{game_id}/copies/{copy_id}")
async def delete_copy(game_id: int, copy_id: int,
                      ac: ActiveCollection = Depends(active_collection)):
    require_write(ac)
    with get_db() as db:
        if not _game_in_collection(db, game_id, ac.id):
            raise not_found("Game not found")
        existing = db.execute(
            "SELECT id FROM game_copies WHERE id = ? AND game_id = ?", (copy_id, game_id)
        ).fetchone()
        if not existing:
            raise not_found("Copy not found")
        count = db.execute(
            "SELECT COUNT(*) FROM game_copies WHERE game_id = ?", (game_id,)
        ).fetchone()[0]
        if count <= 1:
            db.execute("DELETE FROM games WHERE id = ?", (game_id,))
            db.commit()
            return {"message": "Game deleted", "game_deleted": True}
        db.execute("DELETE FROM game_copies WHERE id = ?", (copy_id,))
        db.commit()
        return {"message": "Copy deleted", "game_deleted": False}


@router.get("/api/platforms")
async def list_platforms(_user: CurrentUser = Depends(get_current_user)):
    with get_db() as db:
        cursor = db.execute("SELECT * FROM platforms ORDER BY name")
        return [dict_from_row(row) for row in cursor.fetchall()]


@router.post("/api/platforms")
async def create_platform(platform: PlatformCreate,
                          _user: CurrentUser = Depends(get_current_user)):
    with get_db() as db:
        try:
            cursor = db.execute(
                "INSERT INTO platforms (name, manufacturer, type) VALUES (?, ?, ?)",
                (platform.name, platform.manufacturer, platform.type),
            )
            db.commit()
            return {"id": cursor.lastrowid, "message": "Platform created successfully"}
        except sqlite3.IntegrityError:
            raise conflict("Platform already exists")
