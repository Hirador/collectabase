"""
System catalog: maps Redump datfile slugs (and, later, No-Intro systems) to the
internal platform names used in the ``platforms`` table.

Redump exposes one datfile per system at::

    http://redump.org/datfile/{slug}/serial,version

The importer iterates this list and tolerates per-system failures (a bad/renamed
slug just 404s and is skipped), so an over-broad list is safe -- it can never
break the whole update run.

``platform_name`` is the best-effort mapping to an internal platform; ``None``
means the entries are still imported and searchable but don't map to one of the
collection's known platforms.
"""
from typing import Dict, List, Optional, TypedDict


class SystemDef(TypedDict):
    source: str
    system: str               # source-specific slug
    platform_name: Optional[str]
    url: str


# (redump slug, internal platform name)
REDUMP_SYSTEMS: List[tuple] = [
    # --- Sony ---
    # NB: redump does not publish public datfiles for current-gen discs
    # (PS4/PS5/Xbox One/Wii U all return an error page), so those are covered by
    # IGDB in the lookup flow instead.
    ("psx", "PlayStation"),
    ("ps2", "PlayStation 2"),
    ("ps3", "PlayStation 3"),
    ("psp", "PSP"),
    # --- Microsoft ---
    ("xbox", "Xbox"),
    ("xbox360", "Xbox 360"),
    # --- Nintendo ---
    ("gc", "GameCube"),
    ("wii", "Wii"),
    # --- Sega ---
    ("dc", "Sega Dreamcast"),
    ("ss", "Sega Saturn"),
    ("mcd", "Sega Mega CD & Sega CD"),
    # --- PC / Mac ---
    ("pc", "PC"),
    ("mac", "Apple Macintosh"),
    ("fmt", "Fujitsu FM Towns"),
    ("pc-88", "NEC PC-88"),
    ("pc-98", "NEC PC-98"),
    ("pc-fx", "NEC PC-FX"),
    ("x68k", "Sharp X68000"),
    # --- CD-based others ---
    ("pce", "NEC PC Engine CD & TurboGrafx CD"),
    ("3do", "Panasonic 3DO"),
    ("cdi", "Philips CD-i"),
    ("ngcd", "SNK Neo Geo CD"),
    ("cd32", "Commodore Amiga CD32"),
    ("cdtv", "Commodore Amiga CDTV"),
    ("acd", "Commodore Amiga CD"),
    ("ajcd", "Atari Jaguar CD"),
    ("pippin", "Apple/Bandai Pippin"),
    ("vis", "Tandy/Memorex VIS"),
    ("hs", "Mattel HyperScan"),
    ("ixl", "Fisher-Price iXL"),
    ("nuon", "VM Labs NUON"),
    ("vflash", "VTech V.Flash"),
    ("photo-cd", "Photo CD"),
]


def redump_url(slug: str) -> str:
    return f"http://redump.org/datfile/{slug}/serial,version"


# --- No-Intro (cartridge / handheld) --------------------------------------
#
# No-Intro has no clean per-system download (datomatic needs an interactive
# prepare flow), so we use the daily community mirror, which bundles one .dat
# per system into a single zip. Many No-Intro DATs carry serials as a
# ``<rom serial="...">`` attribute (strong on N64/Genesis/3DS/GBA, weaker on
# SNES/DS); where absent, IGDB fills the gap in the lookup flow.
#
# Keys are the EXACT base system name (the part before the " (timestamp).dat"
# suffix) so variant files like "(Encrypted)" / "(e-Reader)" / "(Multiboot)"
# are not matched unless explicitly listed. We pick the canonical variant.
NO_INTRO_ZIP_URL = (
    "https://github.com/hugo19941994/auto-datfile-generator/"
    "releases/latest/download/no-intro.zip"
)

# (exact No-Intro base system name, internal platform name)
NO_INTRO_SYSTEMS: List[tuple] = [
    # --- Nintendo ---
    ("Nintendo - Nintendo Entertainment System (Headerless)", "NES"),
    ("Nintendo - Super Nintendo Entertainment System", "SNES"),
    ("Nintendo - Nintendo 64 (BigEndian)", "Nintendo 64"),
    ("Nintendo - Game Boy", "Game Boy"),
    ("Nintendo - Game Boy Color", "Game Boy Color"),
    ("Nintendo - Game Boy Advance", "Game Boy Advance"),
    ("Nintendo - Nintendo DS (Decrypted)", "Nintendo DS"),
    ("Nintendo - Nintendo 3DS (Decrypted)", "Nintendo 3DS"),
    ("Nintendo - New Nintendo 3DS (Decrypted)", "Nintendo 3DS"),
    ("Nintendo - Virtual Boy", "Nintendo Virtual Boy"),
    ("Nintendo - Pokemon Mini", "Nintendo Pokemon Mini"),
    # --- Sega ---
    ("Sega - Mega Drive - Genesis", "Sega Genesis/Mega Drive"),
    ("Sega - Master System - Mark III", "Sega Master System"),
    ("Sega - Game Gear", "Sega Game Gear"),
    ("Sega - 32X", "Sega 32X"),
    ("Sega - SG-1000 - SC-3000", "Sega SG-1000"),
    ("Sega - PICO", "Sega Pico"),
    # --- Other handhelds / consoles ---
    ("Bandai - WonderSwan", "Bandai WonderSwan"),
    ("Bandai - WonderSwan Color", "Bandai WonderSwan Color"),
    ("SNK - NeoGeo Pocket", "SNK Neo Geo Pocket"),
    ("SNK - NeoGeo Pocket Color", "SNK Neo Geo Pocket Color"),
    ("NEC - PC Engine - TurboGrafx-16", "NEC PC Engine / TurboGrafx-16"),
    ("Coleco - ColecoVision", "ColecoVision"),
    ("GCE - Vectrex", "Vectrex"),
    ("Mattel - Intellivision", "Mattel Intellivision"),
    ("Atari - Atari 2600", "Atari 2600"),
    ("Atari - Atari 5200", "Atari 5200"),
    ("Atari - Atari 7800 (BIN)", "Atari 7800"),
    ("Atari - Atari Lynx (LNX)", "Atari Lynx"),
    ("Atari - Atari Jaguar (J64)", "Atari Jaguar"),
]


# --- niemasd GameDB (current-gen / cart serial DBs) ------------------------
#
# Clean, GitHub-released TSV databases for systems Redump/No-Intro don't cover
# publicly. Switch ships the printed cart product code (LA-H-xxxxx) plus region.
# Schema: ID<tab>title<tab>region<tab>serial. Auto-updated daily via the
# /releases/latest/download/ asset URL.
#
# (gamedb system name, internal platform name, compiled-TSV URL)
GAMEDB_SYSTEMS: List[tuple] = [
    (
        "Nintendo Switch",
        "Nintendo Switch",
        "https://github.com/niemasd/GameDB-Switch/releases/latest/download/Switch.data.tsv",
    ),
]


def redump_systems() -> List[SystemDef]:
    return [
        {"source": "redump", "system": slug, "platform_name": platform, "url": redump_url(slug)}
        for slug, platform in REDUMP_SYSTEMS
    ]


def no_intro_systems() -> List[SystemDef]:
    return [
        {"source": "no-intro", "system": name, "platform_name": platform, "url": NO_INTRO_ZIP_URL}
        for name, platform in NO_INTRO_SYSTEMS
    ]


def gamedb_systems() -> List[SystemDef]:
    return [
        {"source": "gamedb", "system": name, "platform_name": platform, "url": url}
        for name, platform, url in GAMEDB_SYSTEMS
    ]


def all_systems(sources: Optional[List[str]] = None) -> List[SystemDef]:
    """Return the full set of systems to import, optionally filtered by source."""
    systems: List[SystemDef] = []
    if not sources or "redump" in sources:
        systems.extend(redump_systems())
    if not sources or "no-intro" in sources:
        systems.extend(no_intro_systems())
    if not sources or "gamedb" in sources:
        systems.extend(gamedb_systems())
    return systems


def platform_for(source: str, system: str) -> Optional[str]:
    if source == "redump":
        table = [(s, p) for s, p in REDUMP_SYSTEMS]
    elif source == "gamedb":
        table = [(n, p) for n, p, _ in GAMEDB_SYSTEMS]
    else:
        table = [(n, p) for n, p in NO_INTRO_SYSTEMS]
    for key, platform in table:
        if key == system:
            return platform
    return None
