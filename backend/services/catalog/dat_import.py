"""
Download and import Redump / No-Intro DAT files into the catalog store.

Key behaviours:
  * Redump publishes one zipped Logiqx DAT per system; we stream-parse each to
    keep memory flat even on the large sets (PS2 is ~30 MB of XML).
  * No-Intro has no clean per-system endpoint, so we use the daily community
    mirror, which bundles one .dat per system into a single ~100 MB zip. We
    download it once and import only the curated, allowlisted systems.
  * Serials: Redump uses a ``<serial>`` element; No-Intro uses a
    ``<rom serial="...">`` attribute (ignoring the ``!none`` sentinel).
  * "No rescrape": each DAT carries a header/​filename version. We compare it to
    the last imported version (stored in catalog.db's own ``catalog_meta``) and
    skip re-parsing/re-writing unchanged systems. Catalog updates therefore never
    touch ``games.db``, so they can't contend with the running app or bloat its
    backups.
"""
import csv
import hashlib
import html.entities
import io
import re
import time
import zipfile
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import httpx

from . import catalog_db
from .systems import (
    GAMEDB_SYSTEMS,
    NO_INTRO_SYSTEMS,
    NO_INTRO_ZIP_URL,
    SystemDef,
    gamedb_systems,
    no_intro_systems,
    redump_systems,
)

ProgressCb = Optional[Callable[[int, int, SystemDef], None]]

# redump.org throttles aggressively (~70 KB/s) and intermittently refuses rapid
# sequential requests, so downloads need a generous timeout, retries with
# backoff, and a polite gap between systems.
_DOWNLOAD_TIMEOUT = 300.0
_MAX_RETRIES = 4
_RETRY_BACKOFF = [5, 15, 30, 45]
_POLITE_DELAY = 2.0


def _download(url: str, headers: Dict[str, str]):
    """GET with retries/backoff. Returns the httpx.Response (incl. 304) or raises
    the last exception after exhausting retries."""
    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            with httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"retryable {resp.status_code}", request=resp.request, response=resp
                )
            return resp
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF[attempt])
    raise last_exc  # type: ignore[misc]

# --- name parsing ----------------------------------------------------------

_REGION_WORDS = {
    "usa", "europe", "japan", "world", "asia", "australia", "austria", "belgium",
    "brazil", "canada", "china", "croatia", "czech", "denmark", "finland", "france",
    "germany", "greece", "hong kong", "hungary", "india", "ireland", "israel",
    "italy", "korea", "latin america", "mexico", "netherlands", "new zealand",
    "norway", "poland", "portugal", "russia", "scandinavia", "south africa",
    "spain", "sweden", "switzerland", "taiwan", "thailand", "turkey", "uk",
    "united kingdom", "unknown", "ussr",
}
_LANG_RE = re.compile(r"^[A-Z][a-z]{1,3}(?:,[A-Z][a-z]{1,3})*$")
_REV_RE = re.compile(r"^(?:Rev\b.*|v\d.*|Version\b.*|Alt.*|Beta.*|Proto.*)$", re.IGNORECASE)
_PAREN_RE = re.compile(r"\(([^()]*)\)")
_NO_INTRO_MEMBER_RE = re.compile(r"^(.*) \(\d{8}-\d{6}\)\.dat$")


def parse_dat_name(name: str) -> Dict[str, Optional[str]]:
    """Split a Logiqx game name into title / region / languages / revision / edition.

    e.g. "Diddy Kong Racing (USA) (En,Fr) (Rev 1)"
         -> title='Diddy Kong Racing', region='USA', languages='En,Fr', revision='Rev 1'
    """
    groups = _PAREN_RE.findall(name)
    region: Optional[str] = None
    languages: Optional[str] = None
    revision: Optional[str] = None
    edition: List[str] = []

    for g in groups:
        g = g.strip()
        if not g:
            continue
        parts = [p.strip().lower() for p in g.split(",")]
        if region is None and any(p in _REGION_WORDS for p in parts):
            region = g
        elif languages is None and _LANG_RE.match(g):
            languages = g
        elif revision is None and _REV_RE.match(g):
            revision = g
        else:
            edition.append(g)

    title = _PAREN_RE.sub("", name)
    title = re.sub(r"\s{2,}", " ", title).strip()

    return {
        "title": title,
        "region": region,
        "languages": languages,
        "revision": revision,
        "edition": ", ".join(edition) or None,
    }


# --- DAT parsing -----------------------------------------------------------

def _extract_serial(elem) -> Optional[str]:
    """Redump: <serial> element. No-Intro: <rom serial="..."> attribute."""
    serial_el = elem.find("serial")
    if serial_el is not None and serial_el.text and serial_el.text.strip():
        return serial_el.text.strip()
    for rom in elem.findall("rom"):
        s = (rom.get("serial") or "").strip()
        if s and s.lower() != "!none":
            return s
    return None


_XML_BUILTIN_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
_NAMED_ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]*);")
_BARE_AMP_RE = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)")
# Characters illegal in XML 1.0 (control chars outside tab/LF/CR).
_INVALID_XML_CHARS = re.compile("[^\t\n\r\x20-\ud7ff\ue000-\ufffd]")


def _sanitize_xml(data: bytes) -> bytes:
    """Make a real-world DAT parseable by the strict stdlib parser.

    Redump/No-Intro DATs occasionally embed HTML named entities (e.g. ``&bull;``
    in a header), bare ampersands, or stray control characters that a
    non-validating XML parser rejects. We convert known HTML entities to numeric
    refs, escape leftover ampersands, and drop illegal characters.
    """
    text = data.decode("utf-8", errors="replace")

    def _ent(m: "re.Match") -> str:
        name = m.group(1)
        if name in _XML_BUILTIN_ENTITIES:
            return m.group(0)
        cp = html.entities.name2codepoint.get(name)
        return f"&#{cp};" if cp is not None else m.group(0)

    text = _NAMED_ENTITY_RE.sub(_ent, text)
    text = _BARE_AMP_RE.sub("&amp;", text)
    text = _INVALID_XML_CHARS.sub("", text)
    return text.encode("utf-8")


def parse_dat_xml(xml_bytes: bytes) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Stream-parse a Logiqx DAT. Returns (header_version, entries)."""
    header_version: Optional[str] = None
    entries: List[Dict[str, Any]] = []

    context = ET.iterparse(io.BytesIO(_sanitize_xml(xml_bytes)), events=("end",))
    for _, elem in context:
        tag = elem.tag
        if tag == "version" and header_version is None and elem.text:
            header_version = elem.text.strip()  # first <version> is the header's
        elif tag in ("game", "machine"):
            name = elem.get("name") or ""
            if not name:
                elem.clear()
                continue
            category_el = elem.find("category")
            rev_el = elem.find("version")
            parsed = parse_dat_name(name)
            if rev_el is not None and rev_el.text and not parsed["revision"]:
                parsed["revision"] = rev_el.text.strip()
            entries.append(
                {
                    "full_name": name,
                    "title": parsed["title"],
                    "serial": _extract_serial(elem),
                    "region": parsed["region"],
                    "languages": parsed["languages"],
                    "revision": parsed["revision"],
                    "edition": parsed["edition"],
                    "category": category_el.text.strip() if category_el is not None and category_el.text else None,
                }
            )
            elem.clear()

    return header_version, entries


def _unzip_member(content: bytes, member: Optional[str] = None) -> bytes:
    """Return XML bytes from a zip. If ``member`` is given, read that file;
    otherwise read the first .dat/.xml member. Non-zip content is returned as-is.
    """
    if content[:2] != b"PK":
        return content
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        if member is None:
            names = zf.namelist()
            member = next(
                (n for n in names if n.lower().endswith((".dat", ".xml"))),
                names[0] if names else None,
            )
        if not member:
            return b""
        return zf.read(member)


# --- metadata keys ---------------------------------------------------------

def _meta_key(source: str, system: str, suffix: str) -> str:
    return f"catalog:{source}:{system}:{suffix}"


def _new_result(system: SystemDef) -> Dict[str, Any]:
    return {
        "source": system["source"],
        "system": system["system"],
        "platform_name": system["platform_name"],
        "status": "skipped",
        "entries": 0,
        "version": None,
        "error": None,
    }


# --- Redump: one zipped DAT per system -------------------------------------

def fetch_and_import_system(system: SystemDef, *, force: bool = False) -> Dict[str, Any]:
    """Download, parse and import a single (Redump) system."""
    source, slug = system["source"], system["system"]
    result = _new_result(system)
    if not system.get("url"):
        return result

    etag_key = _meta_key(source, slug, "etag")
    ver_key = _meta_key(source, slug, "version")
    prev_etag = None if force else catalog_db.meta_get(etag_key)
    prev_version = None if force else catalog_db.meta_get(ver_key)

    headers = {"User-Agent": "collectabase-catalog/1.0"}
    if prev_etag:
        headers["If-None-Match"] = prev_etag

    try:
        resp = _download(system["url"], headers)
        if resp.status_code == 304:
            result["status"] = "unchanged"
            result["version"] = prev_version
            return result
        resp.raise_for_status()
        content = resp.content
        etag = resp.headers.get("ETag")

        # Redump DATs are always zips; an HTML body means the slug is unavailable
        # (redump serves a generic error page). Never let that masquerade as data.
        if content[:2] != b"PK":
            raise ValueError("non-DAT response (HTML error page); slug unavailable")

        xml_bytes = _unzip_member(content)
        if not xml_bytes:
            raise ValueError("empty or unreadable DAT archive")

        header_version, entries = parse_dat_xml(xml_bytes)
        result["version"] = header_version

        # Guard against silently wiping a system with an empty/garbage parse.
        if not entries:
            raise ValueError("DAT parsed but contained 0 entries")

        if not force and header_version and header_version == prev_version:
            result["status"] = "unchanged"
            if etag:
                catalog_db.meta_set(etag_key, etag)
            return result

        count = catalog_db.replace_system(source, slug, system["platform_name"], header_version, entries)
        if etag:
            catalog_db.meta_set(etag_key, etag)
        if header_version:
            catalog_db.meta_set(ver_key, header_version)
        result["status"] = "updated"
        result["entries"] = count
        return result

    except httpx.HTTPStatusError as exc:
        result["status"] = "error"
        result["error"] = f"HTTP {exc.response.status_code}"
    except Exception as exc:  # noqa: BLE001 - per-system isolation
        result["status"] = "error"
        result["error"] = str(exc)[:200]
    return result


# --- No-Intro: one big zip, many systems -----------------------------------

def fetch_and_import_no_intro(
    *, force: bool = False, progress_cb: ProgressCb = None, start_index: int = 0, total: int = 0
) -> List[Dict[str, Any]]:
    """Download the No-Intro mirror zip once and import the allowlisted systems."""
    systems = no_intro_systems()
    etag_key = "catalog:no-intro:_zip:etag"
    prev_etag = None if force else catalog_db.meta_get(etag_key)

    headers = {"User-Agent": "collectabase-catalog/1.0"}
    if prev_etag:
        headers["If-None-Match"] = prev_etag

    # Download the bundle (or confirm it's unchanged).
    try:
        resp = _download(NO_INTRO_ZIP_URL, headers)
        if resp.status_code == 304:
            results = []
            for i, system in enumerate(systems):
                if progress_cb:
                    progress_cb(start_index + i, total, system)
                r = _new_result(system)
                r["status"] = "unchanged"
                r["version"] = catalog_db.meta_get(_meta_key("no-intro", system["system"], "version"))
                results.append(r)
            return results
        resp.raise_for_status()
        zip_bytes = resp.content
        etag = resp.headers.get("ETag")
    except Exception as exc:  # noqa: BLE001 - whole No-Intro phase failed
        results = []
        for i, system in enumerate(systems):
            if progress_cb:
                progress_cb(start_index + i, total, system)
            r = _new_result(system)
            r["status"] = "error"
            r["error"] = f"mirror download failed: {str(exc)[:120]}"
            results.append(r)
        return results

    # Map each member file to its base system name.
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        members: Dict[str, str] = {}
        for fn in zf.namelist():
            m = _NO_INTRO_MEMBER_RE.match(fn)
            if m:
                members[m.group(1)] = fn

        results = []
        for i, system in enumerate(systems):
            if progress_cb:
                progress_cb(start_index + i, total, system)
            result = _new_result(system)
            name = system["system"]
            member = members.get(name)
            if not member:
                result["status"] = "error"
                result["error"] = "system not found in mirror zip"
                results.append(result)
                continue

            ver_key = _meta_key("no-intro", name, "version")
            prev_version = None if force else catalog_db.meta_get(ver_key)
            # The timestamp embedded in the filename is the system DAT version.
            fn_match = re.search(r"\((\d{8}-\d{6})\)\.dat$", member)
            file_version = fn_match.group(1) if fn_match else None
            result["version"] = file_version

            if not force and file_version and file_version == prev_version:
                result["status"] = "unchanged"
                results.append(result)
                continue

            try:
                xml_bytes = zf.read(member)
                header_version, entries = parse_dat_xml(xml_bytes)
                version = file_version or header_version
                count = catalog_db.replace_system(
                    "no-intro", name, system["platform_name"], version, entries
                )
                if version:
                    catalog_db.meta_set(ver_key, version)
                result["status"] = "updated"
                result["entries"] = count
                result["version"] = version
            except Exception as exc:  # noqa: BLE001
                result["status"] = "error"
                result["error"] = str(exc)[:200]
            results.append(result)

    if etag:
        catalog_db.meta_set(etag_key, etag)
    return results


# --- GameDB: tab-separated serial DBs (current-gen / carts) ----------------

def parse_gamedb_tsv(data: bytes) -> List[Dict[str, Any]]:
    """Parse a niemasd GameDB TSV (columns: ID, title, region, serial)."""
    text = data.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    entries: List[Dict[str, Any]] = []
    for row in reader:
        title = (row.get("title") or "").strip()
        if not title:
            continue
        entries.append(
            {
                "full_name": title,
                "title": title,
                "serial": (row.get("serial") or "").strip() or None,
                "region": (row.get("region") or "").strip() or None,
                "languages": None,
                "revision": None,
                "edition": None,
                "category": None,
            }
        )
    return entries


def fetch_and_import_gamedb(system: SystemDef, *, force: bool = False) -> Dict[str, Any]:
    """Download and import a single GameDB TSV. The compiled file carries no
    version header, so we key the skip on a content hash."""
    name = system["system"]
    result = _new_result(system)
    ver_key = _meta_key("gamedb", name, "version")
    prev_version = None if force else catalog_db.meta_get(ver_key)
    headers = {"User-Agent": "collectabase-catalog/1.0"}

    try:
        resp = _download(system["url"], headers)
        resp.raise_for_status()
        content = resp.content
        if not content.strip():
            raise ValueError("empty GameDB response")

        version = hashlib.sha1(content).hexdigest()[:16]
        result["version"] = version
        if not force and version == prev_version:
            result["status"] = "unchanged"
            return result

        entries = parse_gamedb_tsv(content)
        if not entries:
            raise ValueError("GameDB parsed but contained 0 entries")
        count = catalog_db.replace_system("gamedb", name, system["platform_name"], version, entries)
        catalog_db.meta_set(ver_key, version)
        result["status"] = "updated"
        result["entries"] = count
    except httpx.HTTPStatusError as exc:
        result["status"] = "error"
        result["error"] = f"HTTP {exc.response.status_code}"
    except Exception as exc:  # noqa: BLE001
        result["status"] = "error"
        result["error"] = str(exc)[:200]
    return result


# --- orchestration ---------------------------------------------------------

def update_catalog(
    *, force: bool = False, sources: Optional[List[str]] = None, progress_cb: ProgressCb = None
) -> Dict[str, Any]:
    """Import every configured system. ``progress_cb(done, total, system)`` is
    invoked before each system so a job tracker can report progress.
    """
    catalog_db.init_catalog_db()

    do_redump = not sources or "redump" in sources
    do_no_intro = not sources or "no-intro" in sources
    do_gamedb = not sources or "gamedb" in sources
    redump = redump_systems() if do_redump else []
    gamedb = gamedb_systems() if do_gamedb else []
    total = len(redump) + (len(NO_INTRO_SYSTEMS) if do_no_intro else 0) + len(gamedb)

    results: List[Dict[str, Any]] = []
    idx = 0
    for system in redump:
        if progress_cb:
            progress_cb(idx, total, system)
        results.append(fetch_and_import_system(system, force=force))
        idx += 1
        if idx < len(redump):
            time.sleep(_POLITE_DELAY)  # be gentle with redump.org's rate limiting

    if do_no_intro:
        results.extend(
            fetch_and_import_no_intro(
                force=force, progress_cb=progress_cb, start_index=idx, total=total
            )
        )
        idx += len(NO_INTRO_SYSTEMS)

    for system in gamedb:
        if progress_cb:
            progress_cb(idx, total, system)
        results.append(fetch_and_import_gamedb(system, force=force))
        idx += 1

    updated = sum(1 for r in results if r["status"] == "updated")
    unchanged = sum(1 for r in results if r["status"] == "unchanged")
    errors = sum(1 for r in results if r["status"] == "error")

    if updated:
        catalog_db.rebuild_fts()

    finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    catalog_db.meta_set("catalog_last_update_at", finished_at)
    catalog_db.meta_set("catalog_last_update_updated", str(updated))
    catalog_db.meta_set("catalog_last_update_errors", str(errors))

    return {
        "finished_at": finished_at,
        "total_systems": total,
        "updated": updated,
        "unchanged": unchanged,
        "errors": errors,
        "results": results,
    }
