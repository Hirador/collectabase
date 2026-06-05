from fastapi import APIRouter, Depends

from ...database import dict_from_row, get_db
from ...auth.deps import ActiveCollection, active_collection

router = APIRouter()


@router.get("/api/stats")
async def get_stats(ac: ActiveCollection = Depends(active_collection)):
    cid = ac.id
    with get_db() as db:
        total_games = db.execute(
            "SELECT COUNT(*) FROM games WHERE is_wishlist = 0 AND collection_id = ?", (cid,)
        ).fetchone()[0]
        # Value = sum of all copy current_values (only copies with a value set count)
        total_value = db.execute(
            """SELECT COALESCE(SUM(gc.current_value), 0)
               FROM game_copies gc JOIN games g ON gc.game_id = g.id
               WHERE g.is_wishlist = 0 AND g.collection_id = ? AND gc.current_value IS NOT NULL""",
            (cid,),
        ).fetchone()[0]
        purchase_value = db.execute(
            """SELECT COALESCE(SUM(gc.purchase_price), 0)
               FROM game_copies gc JOIN games g ON gc.game_id = g.id
               WHERE g.is_wishlist = 0 AND g.collection_id = ? AND gc.purchase_price IS NOT NULL""",
            (cid,),
        ).fetchone()[0]
        wishlist_count = db.execute(
            "SELECT COUNT(*) FROM games WHERE is_wishlist = 1 AND collection_id = ?", (cid,)
        ).fetchone()[0]

        cursor = db.execute(
            """
            SELECT COALESCE(p.name, 'No Platform') as name,
                   COUNT(DISTINCT g.id) as count,
                   COALESCE(SUM(gc.current_value), 0) as value,
                   COALESCE(SUM(gc.purchase_price), 0) as invested
            FROM games g
            LEFT JOIN platforms p ON g.platform_id = p.id
            LEFT JOIN game_copies gc ON gc.game_id = g.id
            WHERE g.is_wishlist = 0 AND g.collection_id = ?
              AND COALESCE(g.item_type, 'game') IN ('game', 'console', 'controller', 'accessory')
            GROUP BY p.name
            ORDER BY count DESC
            """,
            (cid,),
        )
        by_platform = []
        for row in cursor.fetchall():
            item = dict_from_row(row)
            value = float(item.get("value") or 0)
            invested = float(item.get("invested") or 0)
            item["value"] = round(value, 2)
            item["invested"] = round(invested, 2)
            item["profit_loss"] = round(value - invested, 2)
            by_platform.append(item)

        cursor = db.execute(
            """
            SELECT gc.condition, COUNT(gc.id) as count
            FROM game_copies gc JOIN games g ON gc.game_id = g.id
            WHERE g.is_wishlist = 0 AND g.collection_id = ? AND gc.condition IS NOT NULL
            GROUP BY gc.condition
            """,
            (cid,),
        )
        by_condition = [dict_from_row(row) for row in cursor.fetchall()]

        cursor = db.execute(
            """
            SELECT g.item_type, COUNT(DISTINCT g.id) as count,
                   COALESCE(SUM(gc.current_value), 0) as value,
                   COALESCE(SUM(gc.purchase_price), 0) as invested
            FROM games g
            LEFT JOIN game_copies gc ON gc.game_id = g.id
            WHERE g.is_wishlist = 0 AND g.collection_id = ?
            GROUP BY g.item_type
            ORDER BY count DESC
            """,
            (cid,),
        )
        by_type = []
        for row in cursor.fetchall():
            item = dict_from_row(row)
            item["value"] = round(float(item.get("value") or 0), 2)
            item["invested"] = round(float(item.get("invested") or 0), 2)
            by_type.append(item)

        cursor = db.execute(
            """
            SELECT g.id, g.title, g.cover_url,
                   COALESCE(SUM(gc.current_value), 0) as current_value,
                   COALESCE(SUM(gc.purchase_price), 0) as purchase_price,
                   COALESCE(SUM(gc.current_value), 0) - COALESCE(SUM(gc.purchase_price), 0) as profit_loss
            FROM games g
            LEFT JOIN game_copies gc ON gc.game_id = g.id
            WHERE g.is_wishlist = 0 AND g.collection_id = ?
            GROUP BY g.id, g.title, g.cover_url
            HAVING COALESCE(SUM(gc.current_value), 0) > 0
            ORDER BY COALESCE(SUM(gc.current_value), 0) DESC
            LIMIT 15
            """,
            (cid,),
        )
        top_valuable = [dict_from_row(row) for row in cursor.fetchall()]

        cursor = db.execute(
            """
            SELECT g.id, g.title, g.cover_url,
                   COALESCE(SUM(gc.current_value), 0) as current_value,
                   COALESCE(SUM(gc.purchase_price), 0) as purchase_price,
                   COALESCE(SUM(gc.current_value), 0) - COALESCE(SUM(gc.purchase_price), 0) as profit_loss,
                   CASE WHEN COALESCE(SUM(gc.purchase_price), 0) > 0
                        THEN ((COALESCE(SUM(gc.current_value), 0) - SUM(gc.purchase_price)) / SUM(gc.purchase_price)) * 100
                        ELSE 0 END as percent_gain
            FROM games g
            LEFT JOIN game_copies gc ON gc.game_id = g.id
            WHERE g.is_wishlist = 0 AND g.collection_id = ?
            GROUP BY g.id, g.title, g.cover_url
            HAVING COALESCE(SUM(gc.purchase_price), 0) > 0
            ORDER BY percent_gain DESC
            LIMIT 15
            """,
            (cid,),
        )
        top_gainers = [dict_from_row(row) for row in cursor.fetchall()]

        lots_overview = []
        lots_summary = {
            "total_lots": 0,
            "item_count": 0,
            "line_item_count": 0,
            "total_cost_basis": 0.0,
            "estimated_total_value": 0.0,
            "net_sales": 0.0,
            "realized_profit": 0.0,
            "remaining_cost_basis": 0.0,
            "expected_remaining_value": 0.0,
            "inventory_cost_basis": 0.0,
            "estimated_inventory_value": 0.0,
            "break_even_gap": 0.0,
        }

        try:
            cursor = db.execute(
                """
                SELECT
                    l.id,
                    l.name,
                    l.purchase_date,
                    COALESCE(l.purchase_price_gross, 0) + COALESCE(l.shipping_in, 0)
                      + COALESCE(l.fees_in, 0) + COALESCE(l.other_costs, 0) AS total_cost_basis,
                    COUNT(li.id) AS line_item_count,
                    COALESCE(SUM(COALESCE(li.quantity, 1)), 0) AS item_count,
                    COALESCE(SUM(COALESCE(li.estimated_value, 0) * COALESCE(li.quantity, 1)), 0) AS estimated_total_value,
                    COALESCE(SUM(CASE WHEN ls.id IS NOT NULL THEN ls.net_proceeds ELSE 0 END), 0) AS net_sales,
                    COALESCE(SUM(CASE WHEN ls.id IS NOT NULL THEN ls.realized_profit ELSE 0 END), 0) AS realized_profit,
                    COALESCE(SUM(CASE WHEN ls.id IS NULL AND COALESCE(li.status, 'inventory') != 'discarded'
                                      THEN COALESCE(li.allocated_cost_basis, 0) ELSE 0 END), 0) AS remaining_cost_basis,
                    COALESCE(SUM(CASE WHEN ls.id IS NULL AND COALESCE(li.status, 'inventory') != 'discarded'
                                      THEN COALESCE(li.estimated_value, 0) * COALESCE(li.quantity, 1) ELSE 0 END), 0) AS expected_remaining_value,
                    COALESCE(SUM(CASE WHEN ls.id IS NULL AND COALESCE(li.status, 'inventory') = 'inventory'
                                      THEN COALESCE(li.allocated_cost_basis, 0) ELSE 0 END), 0) AS inventory_cost_basis,
                    COALESCE(SUM(CASE WHEN ls.id IS NULL AND COALESCE(li.status, 'inventory') = 'inventory'
                                      THEN COALESCE(li.estimated_value, 0) * COALESCE(li.quantity, 1) ELSE 0 END), 0) AS estimated_inventory_value
                FROM lots l
                LEFT JOIN lot_items li ON li.lot_id = l.id
                LEFT JOIN lot_sales ls ON ls.lot_item_id = li.id
                WHERE l.collection_id = ?
                GROUP BY l.id, l.name, l.purchase_date, l.purchase_price_gross, l.shipping_in, l.fees_in, l.other_costs
                ORDER BY realized_profit DESC, net_sales DESC, l.updated_at DESC
                """,
                (cid,),
            )
            for row in cursor.fetchall():
                item = dict_from_row(row)
                total_cost_basis = round(float(item.get("total_cost_basis") or 0), 2)
                estimated_total_value = round(float(item.get("estimated_total_value") or 0), 2)
                net_sales_value = round(float(item.get("net_sales") or 0), 2)
                realized_profit_value = round(float(item.get("realized_profit") or 0), 2)
                remaining_cost_basis_value = round(float(item.get("remaining_cost_basis") or 0), 2)
                expected_remaining_value = round(float(item.get("expected_remaining_value") or 0), 2)
                inventory_cost_basis = round(float(item.get("inventory_cost_basis") or 0), 2)
                estimated_inventory_value = round(float(item.get("estimated_inventory_value") or 0), 2)
                lots_overview.append(
                    {
                        **item,
                        "total_cost_basis": total_cost_basis,
                        "estimated_total_value": estimated_total_value,
                        "net_sales": net_sales_value,
                        "realized_profit": realized_profit_value,
                        "remaining_cost_basis": remaining_cost_basis_value,
                        "expected_remaining_value": expected_remaining_value,
                        "inventory_cost_basis": inventory_cost_basis,
                        "estimated_inventory_value": estimated_inventory_value,
                        "break_even_gap": round(max(total_cost_basis - net_sales_value, 0), 2),
                        "recovery_rate_pct": round((net_sales_value / total_cost_basis) * 100, 1) if total_cost_basis else 0.0,
                    }
                )

            if lots_overview:
                lots_summary = {
                    "total_lots": len(lots_overview),
                    "item_count": int(sum(int(item.get("item_count") or 0) for item in lots_overview)),
                    "line_item_count": int(sum(int(item.get("line_item_count") or 0) for item in lots_overview)),
                    "total_cost_basis": round(sum(item["total_cost_basis"] for item in lots_overview), 2),
                    "estimated_total_value": round(sum(item["estimated_total_value"] for item in lots_overview), 2),
                    "net_sales": round(sum(item["net_sales"] for item in lots_overview), 2),
                    "realized_profit": round(sum(item["realized_profit"] for item in lots_overview), 2),
                    "remaining_cost_basis": round(sum(item["remaining_cost_basis"] for item in lots_overview), 2),
                    "expected_remaining_value": round(sum(item["expected_remaining_value"] for item in lots_overview), 2),
                    "inventory_cost_basis": round(sum(item["inventory_cost_basis"] for item in lots_overview), 2),
                    "estimated_inventory_value": round(sum(item["estimated_inventory_value"] for item in lots_overview), 2),
                    "break_even_gap": round(sum(item["break_even_gap"] for item in lots_overview), 2),
                }
        except Exception:
            lots_overview = []

    return {
        "total_games": total_games,
        "total_value": round(total_value, 2),
        "purchase_value": round(purchase_value, 2),
        "profit_loss": round(total_value - purchase_value, 2),
        "wishlist_count": wishlist_count,
        "by_platform": by_platform,
        "by_condition": by_condition,
        "by_type": by_type,
        "top_valuable": top_valuable,
        "top_gainers": top_gainers,
        "lots_summary": lots_summary,
        "lots_overview": lots_overview,
    }


@router.get("/api/stats/history")
async def get_stats_history(days: int = 30, ac: ActiveCollection = Depends(active_collection)):
    with get_db() as db:
        cursor = db.execute(
            """
            SELECT recorded_at, total_value, game_value, hardware_value
            FROM value_history
            WHERE collection_id = ?
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (ac.id, days),
        )
        rows = cursor.fetchall()

    history = []
    for row in reversed(rows):
        item = dict_from_row(row)
        history.append({
            "date": item["recorded_at"],
            "total": round(item.get("total_value") or 0, 2),
            "games": round(item.get("game_value") or 0, 2),
            "hardware": round(item.get("hardware_value") or 0, 2),
        })

    return history
