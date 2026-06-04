"""
Standalone SQLite store for the disc/cartridge catalog imported from Redump and
No-Intro DAT files.

This lives in its own database file (``catalog.db``) next to ``games.db`` so the
(large, fully re-downloadable) catalog never bloats the user's ``games.db`` or the
Docker/SQLite backups. It is intentionally NOT managed by SQLAlchemy/Alembic --
the schema is plain ``CREATE TABLE IF NOT EXISTS`` and the data is rebuilt by the
catalog updater rather than migrated.
"""
import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional


def get_data_dir() -> str:
    """Mirror the logic in db/session.py so catalog.db sits beside games.db.

    An explicit ``CATALOG_DATA_DIR`` always wins (used in tests and custom
    deployments); otherwise use the Docker data volume, falling back to the local
    source tree for development.
    """
    override = os.getenv("CATALOG_DATA_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    if os.path.exists("/app"):
        return "/app/data"
    local_data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "app",
        "data",
    )
    os.makedirs(local_data_dir, exist_ok=True)
    return local_data_dir


def get_catalog_db_path() -> str:
    return os.path.join(get_data_dir(), "catalog.db")


@contextmanager
def _connect():
    conn = sqlite3.connect(get_catalog_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def normalize_serial(serial: Optional[str]) -> str:
    """Strip spaces/dashes/dots and lowercase so 'SLPM 86770' == 'slpm-86770'."""
    if not serial:
        return ""
    return re.sub(r"[\s\-_.]", "", serial).lower()


def init_catalog_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS disc_catalog (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                source        TEXT NOT NULL,        -- 'redump' | 'no-intro'
                system        TEXT NOT NULL,        -- source-specific system slug
                platform_name TEXT,                 -- mapped internal platform name
                title         TEXT NOT NULL,        -- cleaned title (no tags)
                full_name     TEXT NOT NULL,        -- raw <game name>
                serial        TEXT,                 -- raw serial(s), may be comma-joined
                serial_norm   TEXT,                 -- normalized, comma-joined serials
                region        TEXT,
                languages     TEXT,
                revision      TEXT,
                edition       TEXT,                 -- parsed edition/variant tokens
                category      TEXT,                 -- Games / Demos / Applications ...
                dat_version   TEXT                  -- header <version> of source DAT
            );

            CREATE INDEX IF NOT EXISTS idx_disc_catalog_source_system
                ON disc_catalog(source, system);
            CREATE INDEX IF NOT EXISTS idx_disc_catalog_serial_norm
                ON disc_catalog(serial_norm);
            CREATE INDEX IF NOT EXISTS idx_disc_catalog_platform
                ON disc_catalog(platform_name);

            CREATE VIRTUAL TABLE IF NOT EXISTS disc_catalog_fts USING fts5(
                title,
                full_name,
                serial_norm,
                content='disc_catalog',
                content_rowid='id'
            );

            CREATE TABLE IF NOT EXISTS catalog_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        conn.commit()


def meta_get(key: str, default: Optional[str] = None) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM catalog_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def meta_get_many(keys: List[str]) -> Dict[str, str]:
    if not keys:
        return {}
    placeholders = ",".join("?" for _ in keys)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT key, value FROM catalog_meta WHERE key IN ({placeholders})",
            tuple(keys),
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}


def meta_set(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO catalog_meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()


def replace_system(
    source: str,
    system: str,
    platform_name: Optional[str],
    dat_version: Optional[str],
    entries: Iterable[Dict[str, Any]],
) -> int:
    """Atomically replace every row for (source, system) with ``entries``.

    Each entry dict may contain: full_name, title, serial, region, languages,
    revision, edition, category. Returns the number of rows inserted.
    """
    rows = []
    for e in entries:
        serial = e.get("serial")
        rows.append(
            (
                source,
                system,
                platform_name,
                e.get("title") or e.get("full_name") or "",
                e.get("full_name") or "",
                serial,
                ",".join(
                    normalize_serial(s) for s in (serial.split(",") if serial else []) if s.strip()
                )
                or None,
                e.get("region"),
                e.get("languages"),
                e.get("revision"),
                e.get("edition"),
                e.get("category"),
                dat_version,
            )
        )

    with _connect() as conn:
        conn.execute(
            "DELETE FROM disc_catalog WHERE source = ? AND system = ?",
            (source, system),
        )
        conn.executemany(
            """
            INSERT INTO disc_catalog
                (source, system, platform_name, title, full_name, serial,
                 serial_norm, region, languages, revision, edition, category, dat_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def rebuild_fts() -> None:
    """Rebuild the FTS index from the content table. Call once after a bulk update."""
    with _connect() as conn:
        conn.execute("INSERT INTO disc_catalog_fts(disc_catalog_fts) VALUES('rebuild')")
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


# Sequel numerals vary between sources ("MediEvil II" vs "MediEvil 2"). Treat
# Roman <-> Arabic as equivalent, but only for multi-letter Roman forms — single
# letters (I/V/X) are ambiguous (e.g. "Mega Man X" is NOT "Mega Man 10").
_ROMAN_NUMERALS = {
    1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi", 7: "vii", 8: "viii",
    9: "ix", 10: "x", 11: "xi", 12: "xii", 13: "xiii", 14: "xiv", 15: "xv",
    16: "xvi", 17: "xvii", 18: "xviii", 19: "xix", 20: "xx",
}
_NUM_EQUIV: Dict[str, str] = {}
for _n, _rom in _ROMAN_NUMERALS.items():
    if len(_rom) >= 2:
        _NUM_EQUIV[str(_n)] = _rom
        _NUM_EQUIV[_rom] = str(_n)


def _fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 query, expanding sequel numerals so
    "MediEvil II" also matches "MediEvil 2" (and vice versa)."""
    parts = []
    for t in re.findall(r"[0-9A-Za-z]+", text):
        low = t.lower()
        if low in _NUM_EQUIV:
            parts.append(f"({low} OR {_NUM_EQUIV[low]})")
        else:
            parts.append(f"{t}*")
    return " AND ".join(parts)


def search(
    query: str,
    *,
    limit: int = 25,
    source: Optional[str] = None,
    system: Optional[str] = None,
    platform_name: Optional[str] = None,
    serial_only: bool = False,
) -> List[Dict[str, Any]]:
    """Search the catalog by serial or by title.

    Serial matching is bidirectional and tolerant: it matches when the stored
    serial contains the query (partial entry) OR when the query contains a stored
    serial (a full printed code like ``NTP-AYWP-EIP`` for the stored game code
    ``AYWP``). ``serial_only=True`` forces serial matching and skips the title
    fallback (used by the serial step). Otherwise a serial-looking query (has a
    digit or dash) tries serials first, then falls back to a title FTS match.
    """
    query = (query or "").strip()
    if not query:
        return []

    filters = []
    params: List[Any] = []
    if source:
        filters.append("source = ?")
        params.append(source)
    if system:
        filters.append("system = ?")
        params.append(system)
    if platform_name:
        filters.append("platform_name = ?")
        params.append(platform_name)
    filter_sql = (" AND " + " AND ".join(filters)) if filters else ""

    norm = normalize_serial(query)
    looks_like_serial = bool(re.search(r"[0-9-]", query)) and len(norm) >= 3

    with _connect() as conn:
        if (serial_only or looks_like_serial) and norm:
            rows = conn.execute(
                f"""
                SELECT * FROM disc_catalog
                WHERE serial_norm IS NOT NULL
                  AND ( serial_norm LIKE ?
                        OR (LENGTH(serial_norm) >= 4 AND ? LIKE '%' || serial_norm || '%') )
                  {filter_sql}
                ORDER BY (serial_norm = ?) DESC, LENGTH(serial_norm), title
                LIMIT ?
                """,
                [f"%{norm}%", norm, *params, norm, limit],
            ).fetchall()
            if rows:
                return [_row_to_dict(r) for r in rows]
            if serial_only:
                return []

        match = _fts_query(query)
        if not match:
            return []
        rows = conn.execute(
            f"""
            SELECT c.* FROM disc_catalog c
            JOIN disc_catalog_fts f ON f.rowid = c.id
            WHERE disc_catalog_fts MATCH ? {filter_sql}
            ORDER BY rank
            LIMIT ?
            """,
            [match, *params, limit],
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


# Re-release / packaging keywords that count as a genuine "edition". The parsed
# `edition` column also holds non-edition tags (dates, "Demo", "Disc 1", region
# test names...), so we surface only entries matching these.
_EDITION_KEYWORDS = (
    "platinum", "greatest hits", "player's choice", "players choice", "classics",
    "essentials", "the best", "playstation hits", "nintendo selects", "selects",
    "collector", "limited edition", "game of the year", "goty", "special edition",
    "deluxe", "definitive", "complete edition", "anniversary", "premium",
    "gold edition", "value", "platinum hits", "favorites",
)


def distinct_editions(title: str, *, limit: int = 25) -> List[str]:
    """Distinct genuine edition tags catalogued for a title (e.g. Platinum,
    Greatest Hits). Matches the title loosely so regional name variants still hit,
    and filters out non-edition parentheticals via an edition-keyword whitelist.
    """
    title = (title or "").strip()
    if not title:
        return []
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT edition FROM disc_catalog
            WHERE edition IS NOT NULL AND edition != ''
              AND LOWER(title) LIKE '%' || LOWER(?) || '%'
            ORDER BY edition
            """,
            (title,),
        ).fetchall()
    out: List[str] = []
    seen: set = set()
    for r in rows:
        # The edition column may concatenate several tags ("Disc 1, Premium
        # Package"); keep only the individual tokens that look like an edition.
        for token in r["edition"].split(", "):
            token = token.strip()
            low = token.lower()
            if token and low not in seen and any(k in low for k in _EDITION_KEYWORDS):
                seen.add(low)
                out.append(token)
        if len(out) >= limit:
            break
    return out


def get_stats() -> Dict[str, Any]:
    """Totals and per-system breakdown for the status endpoint."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM disc_catalog").fetchone()["n"]
        per_system = conn.execute(
            """
            SELECT source, system, platform_name,
                   COUNT(*) AS entries, MAX(dat_version) AS dat_version
            FROM disc_catalog
            GROUP BY source, system
            ORDER BY source, system
            """
        ).fetchall()
    return {
        "total_entries": total,
        "systems": [_row_to_dict(r) for r in per_system],
    }
