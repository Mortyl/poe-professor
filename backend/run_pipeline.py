"""
PoEProfessor Pipeline Runner
-----------------------------
Auto-discovers all viable skill/ascendancy combos from poe.ninja,
deduplicates by gem tag signature, then runs the full 4-step data
pipeline for each unique combo.

Pipeline steps per combo:
  1. scrape_heatmap.py  — passive tree adoption (9000+ builds)
  2. scrape_poeninja.py — PoB export codes (gear + gem source)
  3. analyse_gear.py    — gear/charm/jewel report
  4. analyse_gems.py    — gem link report

State is tracked in pipeline.db (SQLite) so runs can be interrupted
and safely resumed at any point.

Usage:
  python run_pipeline.py --discover                         # find combos, save to DB, stop
  python run_pipeline.py                                    # discover + run full pipeline (league starter)
  python run_pipeline.py --resume                           # skip discovery, run pending/failed only
  python run_pipeline.py --ascendancy Deadeye               # one ascendancy only
  python run_pipeline.py --status                           # print status table and exit
  python run_pipeline.py --mode endgame                     # full pipeline using week-2 to week-6 snapshots
  python run_pipeline.py --mode endgame --resume            # resume endgame pipeline only
  python run_pipeline.py --mode endgame --ascendancy Deadeye  # one ascendancy, endgame mode
"""

import sys
import os
import json
import time
import random
import sqlite3
import argparse
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DB_PATH       = os.path.join(BASE_DIR, "pipeline.db")
VARIANTS_PATH       = os.path.join(BASE_DIR, "variants.json")
MANUAL_COMBOS_PATH  = os.path.join(BASE_DIR, "manual_combos.json")


# ── Config ─────────────────────────────────────────────────────────────────────

# All released ascendancies (add new ones here as GGG releases them)
ASCENDANCIES = [
    "Deadeye", "Pathfinder",                                # Ranger
    "Infernalist", "Blood Mage", "Lich",                    # Witch
    "Titan", "Warbringer",                                  # Warrior
    "Amazon",                                                # Huntress
    "Stormweaver", "Chronomancer", "Disciple of Varashta",  # Sorceress
    "Invoker", "Acolyte of Chayula",                        # Monk
    "Tactician", "Witchhunter", "Gemling Legionnaire",      # Mercenary
    "Oracle", "Shaman",                                     # Druid
]

# Minimum builds for a combo to be worth scraping
MIN_BUILDS = 50

# Archetype dimensions — two skills with the same (source, delivery, damage_type)
# are considered the same build archetype and deduplicated.
SOURCE_TAGS   = {"attack", "spell", "warcry"}
DELIVERY_TAGS = {
    # Weapon types (from gem_tags.json weapon requirements)
    "bow", "crossbow", "mace", "sword", "axe", "spear", "quarterstaff",
    "staff", "wand", "sceptre", "flail", "claw", "dagger",
    # Delivery mechanics
    "grenade", "totem", "mine", "trap",
    # Shapeshift forms
    "wyvern", "werewolf", "bear",
}
DAMAGE_TAGS   = {"lightning", "cold", "fire", "chaos", "physical", "arcane"}

# Name-based delivery inference — fallback when delivery tag is absent
DELIVERY_NAME_HINTS = {
    "arrow":      "bow",
    "shot":       "ammunition",
    "shards":     "ammunition",
    "rounds":     "ammunition",
    "grenade":    "grenade",
    "explosive":  "grenade",
    "bolt":       "spell",
    "spear":      "spear",
    "lance":      "spear",
}


def get_archetype(skill: str, tags: list[str]) -> tuple[str, str, str] | None:
    """
    Return (source, delivery, damage_type) for a skill, or None if tags are empty.
    Used for dedup — two skills with identical archetype tuples are the same build.
    """
    if not tags:
        return None
    tag_set = set(tags)

    source   = next((t for t in ["attack", "spell", "warcry"] if t in tag_set), "other")
    delivery = next((t for t in DELIVERY_TAGS if t in tag_set), None)
    damage   = next((t for t in DAMAGE_TAGS   if t in tag_set), "none")

    # Infer delivery from skill name if not in tags
    if not delivery:
        skill_lower = skill.lower()
        for hint, inferred in DELIVERY_NAME_HINTS.items():
            if hint in skill_lower:
                delivery = inferred
                break

    # Fallback: if still no delivery but skill is a projectile, use that
    if not delivery:
        if "projectile" in tag_set:
            delivery = "projectile"
        elif "melee" in tag_set:
            delivery = "melee"
        else:
            delivery = "other"

    return (source, delivery, damage)

# Skills whose names contain any of these substrings are non-damage skills and skipped
NON_DAMAGE_PATTERNS = {
    "herald", "aura", "banner", "warcry", "war cry",
    "determination", "grace", "haste", "discipline", "clarity",
    "vitality", "malevolence", "hatred", "wrath", "zealotry",
    "purity", "skitterbots", "flesh and stone", "enlighten",
    "empower", "enhance", "flammability", "conductivity",
    "vulnerability", "frostbite", "enfeeble", "temporal chains",
}

# Skills with ANY of these gem tags are non-damage and skipped
NON_DAMAGE_TAGS = {"buff", "aura", "persistent", "warcry", "curse", "hex"}

# Path to local gem tags file for tag-based deduplication
GEM_TAGS_PATH = os.path.join(BASE_DIR, "gem_tags.json")
FEATURED_UNIQUES_PATH = os.path.join(BASE_DIR, "featured_uniques.json")

# Path to manual secondary skills blocklist
SECONDARY_SKILLS_PATH = os.path.join(BASE_DIR, "secondary_skills.json")

# Minimum builds when queried as PRIMARY skill — filters out support skills
# that appear in many builds but are never the main damage skill
MIN_PRIMARY_BUILDS = 30
MIN_PRIMARY_RATIO  = 0.40   # primary_count / total_count — skills below this are companions spread across builds
MIN_VARIANT_BUILDS = 50    # minimum builds for a variant combo to be worth scraping

# Delay ranges (seconds) — randomised to avoid fixed-interval bot detection
DELAY_API_RANGE         = (3.5, 7.0)    # between individual API calls during discovery
DELAY_COMBO_RANGE       = (10.0, 20.0)  # between finishing one combo and starting the next
DELAY_ASCENDANCY_RANGE  = (20.0, 35.0)  # between ascendancy discovery queries
DELAY_LONG_BREAK_RANGE  = (90.0, 180.0) # periodic long break every N combos
LONG_BREAK_EVERY        = 10            # take a long break after this many combos

# Snapshot ranges for each pipeline step / mode
HEATMAP_SNAPSHOTS          = "day-1,day-2,day-3,day-4"
POB_SNAPSHOTS              = "day-2,day-3,day-4"
HEATMAP_SNAPSHOTS_ENDGAME  = "week-2,week-3,week-4"
POB_SNAPSHOTS_ENDGAME      = "week-2,week-3,week-4"
# Exotic mode pools the widest window — for low-builds combos that don't hit
# popular thresholds in either LS or EG. day-4..week-4 catches both campaign
# clear-ers who never re-uploaded and slow-rampers who built late.
HEATMAP_SNAPSHOTS_EXOTIC   = "day-4,day-5,day-6,week-1,week-2,week-3,week-4"
POB_SNAPSHOTS_EXOTIC       = "day-4,day-5,day-6,week-1,week-2,week-3,week-4"

# Popular thresholds — a combo qualifies as popular in a mode when its
# builds_count for that mode is at or above the matching cutoff. Combos that
# fail both qualify for exotic-bucket processing.
POPULAR_LS_THRESHOLD = 90
POPULAR_EG_THRESHOLD = 150


def load_variants() -> dict[str, list[str]]:
    if os.path.exists(VARIANTS_PATH):
        with open(VARIANTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_manual_combos() -> list[dict]:
    if os.path.exists(MANUAL_COMBOS_PATH):
        with open(MANUAL_COMBOS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


# ── SQLite ──────────────────────────────────────────────────────────────────────

def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Check whether combos table exists and which columns it has
    existing_cols = set()
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='combos'"
    ).fetchone()
    if table_exists:
        existing_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(combos)").fetchall()
        }

    needs_full_rebuild = table_exists and (
        "variant_companion" not in existing_cols or "mode" not in existing_cols
    )

    if needs_full_rebuild:
        # Migrate: rename old table, create new one, copy data, drop old
        missing = [c for c in ("variant_companion", "mode") if c not in existing_cols]
        print(f"  Migrating combos table to add column(s): {', '.join(missing)}...")
        # Drop any leftover combos_old from a previously interrupted migration —
        # without this the ALTER TABLE below fails the second time round.
        conn.execute("DROP TABLE IF EXISTS combos_old")
        conn.execute("ALTER TABLE combos RENAME TO combos_old")
        conn.execute("""
            CREATE TABLE combos (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                skill             TEXT NOT NULL,
                ascendancy        TEXT NOT NULL,
                variant_companion TEXT NOT NULL DEFAULT '',
                mode              TEXT NOT NULL DEFAULT 'league_starter',
                tag_signature     TEXT,
                builds_count      INTEGER DEFAULT 0,
                discovered_at     TEXT,
                last_scraped      TEXT,
                passives_done     INTEGER DEFAULT 0,
                pob_done          INTEGER DEFAULT 0,
                gear_done         INTEGER DEFAULT 0,
                gems_done         INTEGER DEFAULT 0,
                status            TEXT DEFAULT 'pending',
                error_msg         TEXT,
                UNIQUE(skill, ascendancy, variant_companion, mode)
            )
        """)
        # Copy what we can; missing columns default automatically
        old_vc = "''" if "variant_companion" not in existing_cols else "variant_companion"
        conn.execute(f"""
            INSERT INTO combos
                (skill, ascendancy, variant_companion, mode, tag_signature,
                 builds_count, discovered_at, last_scraped,
                 passives_done, pob_done, gear_done, gems_done, status, error_msg)
            SELECT skill, ascendancy, {old_vc}, 'league_starter', tag_signature,
                   builds_count, discovered_at, last_scraped,
                   passives_done, pob_done, gear_done, gems_done, status, error_msg
            FROM combos_old
        """)
        conn.execute("DROP TABLE combos_old")
        conn.commit()
        print("  Migration complete.")
    elif not table_exists:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS combos (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                skill             TEXT NOT NULL,
                ascendancy        TEXT NOT NULL,
                variant_companion TEXT NOT NULL DEFAULT '',
                mode              TEXT NOT NULL DEFAULT 'league_starter',
                tag_signature     TEXT,
                builds_count      INTEGER DEFAULT 0,
                discovered_at     TEXT,
                last_scraped      TEXT,
                passives_done     INTEGER DEFAULT 0,
                pob_done          INTEGER DEFAULT 0,
                gear_done         INTEGER DEFAULT 0,
                gems_done         INTEGER DEFAULT 0,
                status            TEXT DEFAULT 'pending',
                error_msg         TEXT,
                UNIQUE(skill, ascendancy, variant_companion, mode)
            );
        """)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS gem_tags (
            skill      TEXT PRIMARY KEY,
            tags       TEXT,
            fetched_at TEXT
        );
    """)
    conn.commit()
    return conn


def upsert_combo(conn, skill, ascendancy, tag_sig, builds_count,
                 variant_companion: str = '', mode: str = 'league_starter',
                 preserve_tag: bool = False):
    """
    Insert or update a combo row.
    preserve_tag=True: on conflict, update builds_count only — don't overwrite an existing
    tag_signature from normal discovery with a 'unique/...' placeholder.
    """
    now = datetime.now(timezone.utc).isoformat()
    if preserve_tag:
        conn.execute("""
            INSERT INTO combos (skill, ascendancy, variant_companion, mode, tag_signature, builds_count, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(skill, ascendancy, variant_companion, mode) DO UPDATE SET
                builds_count = excluded.builds_count
        """, (skill, ascendancy, variant_companion, mode, tag_sig, builds_count, now))
    else:
        conn.execute("""
            INSERT INTO combos (skill, ascendancy, variant_companion, mode, tag_signature, builds_count, discovered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(skill, ascendancy, variant_companion, mode) DO UPDATE SET
                tag_signature = excluded.tag_signature,
                builds_count  = excluded.builds_count
        """, (skill, ascendancy, variant_companion, mode, tag_sig, builds_count, now))
    conn.commit()


def mark_step(conn, skill, ascendancy, step, ok, error="",
              variant_companion: str = '', mode: str = 'league_starter'):
    col = f"{step}_done"
    now = datetime.now(timezone.utc).isoformat()
    if ok:
        conn.execute(
            f"UPDATE combos SET {col}=1, last_scraped=?, error_msg=NULL "
            f"WHERE skill=? AND ascendancy=? AND variant_companion=? AND mode=?",
            (now, skill, ascendancy, variant_companion, mode)
        )
    else:
        conn.execute(
            f"UPDATE combos SET {col}=0, status='failed', error_msg=?, last_scraped=? "
            f"WHERE skill=? AND ascendancy=? AND variant_companion=? AND mode=?",
            (error[:500], now, skill, ascendancy, variant_companion, mode)
        )
    conn.commit()


def mark_done(conn, skill, ascendancy, variant_companion: str = '', mode: str = 'league_starter'):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE combos SET status='done', last_scraped=? "
        "WHERE skill=? AND ascendancy=? AND variant_companion=? AND mode=?",
        (now, skill, ascendancy, variant_companion, mode)
    )
    conn.commit()


# ── Network + Protobuf (mirrors scrape_heatmap.py) ─────────────────────────────

def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while pos < len(data):
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def parse_fields(data: bytes) -> dict[int, list]:
    pos = 0; n = len(data); fields: dict[int, list] = {}
    while pos < n:
        try:
            tag, pos = read_varint(data, pos)
        except Exception:
            break
        wt = tag & 7; fn = tag >> 3
        if fn not in fields:
            fields[fn] = []
        if wt == 2:
            try:
                length, pos = read_varint(data, pos)
            except Exception:
                break
            fields[fn].append(data[pos:pos + length]); pos += length
        elif wt == 0:
            v, pos = read_varint(data, pos); fields[fn].append(v)
        elif wt == 5:
            fields[fn].append(None); pos += 4
        elif wt == 1:
            fields[fn].append(None); pos += 8
        else:
            break
    return fields


def get_snapshot(league: str = "sc") -> tuple[str, str, list[str]]:
    raw  = fetch("https://poe.ninja/poe2/api/data/index-state")
    data = json.loads(raw)
    for snap in data.get("snapshotVersions", []):
        url    = snap.get("url", "")
        is_hc  = "hc"  in url
        is_ssf = "ssf" in url
        if snap.get("overviewType", 0) != 0:
            continue
        match = (
            (league == "sc"    and not is_hc and not is_ssf) or
            (league == "ssf"   and     is_ssf and not is_hc) or
            (league == "hc"    and     is_hc  and not is_ssf) or
            (league == "hcssf" and     is_hc  and     is_ssf)
        )
        if match:
            return snap["version"], snap["snapshotName"], snap.get("timeMachineLabels", [])
    raise RuntimeError(f"Could not find snapshot for league '{league}'")


# ── Gem tag fetching ────────────────────────────────────────────────────────────

def load_featured_uniques() -> list[str]:
    """Load the list of unique item names to discover builds for."""
    if not os.path.exists(FEATURED_UNIQUES_PATH):
        return []
    try:
        with open(FEATURED_UNIQUES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        items = [u.strip() for u in data if isinstance(u, str) and u.strip()]
        if items:
            print(f"  Loaded {len(items)} featured unique(s) from featured_uniques.json")
        return items
    except Exception as e:
        print(f"  WARNING: could not load featured_uniques.json: {e}")
        return []


def load_gem_tags() -> dict[str, list[str]]:
    """
    Load gem tags from local gem_tags.json for tag-based deduplication.
    poe.ninja has no PoE2 gem tags API — this file is maintained manually.
    Returns {skill_name: [tag, tag, ...]} or {} if file doesn't exist.

    gem_tags.json format:
    {
      "Lightning Arrow":   ["attack", "projectile", "lightning", "bow"],
      "Poisonburst Arrow": ["attack", "projectile", "chaos", "bow"],
      ...
    }
    """
    if not os.path.exists(GEM_TAGS_PATH):
        print("  No gem_tags.json found — tag deduplication disabled")
        print(f"  Create {GEM_TAGS_PATH} to enable it")
        return {}
    try:
        with open(GEM_TAGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        print(f"  Loaded gem tags for {len(data)} skills from gem_tags.json")
        return {k: [t.lower() for t in v] for k, v in data.items()}
    except Exception as e:
        print(f"  WARNING: could not load gem_tags.json: {e}")
        return {}




# ── Discovery ───────────────────────────────────────────────────────────────────

def discover_skills_for_ascendancy(
    ascendancy: str, snapshot: str, snapshot_name: str, label: str,
) -> tuple[dict[str, int], dict[str, int]]:
    """
    Query poe.ninja without a skill filter to get ALL active skills used by
    an ascendancy's builds. Returns ({skill: count}, {all_skill: count}).
    """
    url = (
        f"https://poe.ninja/poe2/api/builds/{snapshot}/search"
        f"?class={urllib.parse.quote(ascendancy)}"
        f"&timemachine={urllib.parse.quote(label)}"
        f"&heatmap=true"
        f"&overview={urllib.parse.quote(snapshot_name)}"
    )
    print(f"  GET {url}")
    try:
        raw = fetch(url)
    except Exception as e:
        print(f"  ERROR fetching: {e}")
        return {}, {}

    outer_f = parse_fields(raw)
    if 1 not in outer_f or not isinstance(outer_f[1][0], bytes):
        print("  ERROR: unexpected proto structure")
        return {}, {}
    inner_f = parse_fields(outer_f[1][0])

    total = inner_f.get(1, [0])[0]
    print(f"  Total builds for {ascendancy}: {total if isinstance(total, int) else '?'}")

    # Find gem dictionary hash
    dict_refs: dict[str, str] = {}
    for ref_bytes in inner_f.get(6, []):
        if not isinstance(ref_bytes, bytes):
            continue
        rf = parse_fields(ref_bytes)
        ref_id   = rf.get(1, [b""])[0].decode("utf-8") if isinstance(rf.get(1, [None])[0], bytes) else ""
        ref_hash = rf.get(2, [b""])[0].decode("utf-8") if isinstance(rf.get(2, [None])[0], bytes) else ""
        if ref_id and ref_hash:
            dict_refs[ref_id] = ref_hash

    if "gem" not in dict_refs:
        print("  No gem dictionary in response — no skills found")
        return {}

    # Fetch gem name dictionary
    time.sleep(random.uniform(*DELAY_API_RANGE))
    gem_url = f"https://poe.ninja/poe2/api/builds/dictionary/{dict_refs['gem']}"
    try:
        gem_raw = fetch(gem_url)
        gf = parse_fields(gem_raw)
        gem_values = [
            v.decode("utf-8") if isinstance(v, bytes) else ""
            for v in gf.get(2, [])
        ]
    except Exception as e:
        print(f"  ERROR fetching gem dictionary: {e}")
        return {}

    # Parse the "skills" dimension (active skills only, not supports)
    active_counts: dict[str, int] = {}
    all_counts:    dict[str, int] = {}

    for dim_bytes in inner_f.get(2, []):
        if not isinstance(dim_bytes, bytes):
            continue
        df = parse_fields(dim_bytes)
        dim_id = df.get(1, [b""])[0].decode("utf-8") if isinstance(df.get(1, [None])[0], bytes) else ""
        if dim_id not in ("skills", "allskills"):
            continue
        target = active_counts if dim_id == "skills" else all_counts
        for cnt_bytes in df.get(3, []):
            if not isinstance(cnt_bytes, bytes):
                continue
            cf = parse_fields(cnt_bytes)
            seq_id = cf.get(1, [0])[0]
            count  = cf.get(2, [0])[0]
            if not isinstance(seq_id, int) or not isinstance(count, int):
                continue
            if seq_id < len(gem_values) and gem_values[seq_id]:
                target[gem_values[seq_id]] = count

    return active_counts, all_counts


def fetch_primary_data(
    ascendancy: str, skill: str,
    snapshot: str, snapshot_name: str, label: str,
    gem_dict_cache: dict[str, list[str]],
) -> tuple[int, dict[str, int]]:
    """
    Query poe.ninja WITH a skill filter.
    Returns (primary_count, {companion_skill: count}) for companion detection.
    companion_skill counts come from the allskills dimension.
    """
    skill_enc = urllib.parse.quote(skill.replace(" ", "+"), safe="+")
    url = (
        f"https://poe.ninja/poe2/api/builds/{snapshot}/search"
        f"?class={urllib.parse.quote(ascendancy)}"
        f"&skills={skill_enc}"
        f"&timemachine={urllib.parse.quote(label)}"
        f"&heatmap=true"
        f"&overview={urllib.parse.quote(snapshot_name)}"
    )
    try:
        raw     = fetch(url)
        outer_f = parse_fields(raw)
        if 1 not in outer_f or not isinstance(outer_f[1][0], bytes):
            return 0, {}
        inner_f = parse_fields(outer_f[1][0])
        total   = inner_f.get(1, [0])[0]
        if not isinstance(total, int):
            return 0, {}

        # Get gem dictionary (cached)
        dict_refs: dict[str, str] = {}
        for ref_bytes in inner_f.get(6, []):
            if not isinstance(ref_bytes, bytes):
                continue
            rf = parse_fields(ref_bytes)
            ref_id   = rf.get(1, [b""])[0].decode("utf-8") if isinstance(rf.get(1, [None])[0], bytes) else ""
            ref_hash = rf.get(2, [b""])[0].decode("utf-8") if isinstance(rf.get(2, [None])[0], bytes) else ""
            if ref_id and ref_hash:
                dict_refs[ref_id] = ref_hash

        gem_values: list[str] = []
        if "gem" in dict_refs:
            gem_hash = dict_refs["gem"]
            if gem_hash in gem_dict_cache:
                gem_values = gem_dict_cache[gem_hash]
            else:
                try:
                    gem_raw = fetch(f"https://poe.ninja/poe2/api/builds/dictionary/{gem_hash}")
                    gf = parse_fields(gem_raw)
                    gem_values = [v.decode("utf-8") if isinstance(v, bytes) else "" for v in gf.get(2, [])]
                    gem_dict_cache[gem_hash] = gem_values
                except Exception:
                    pass

        # Parse allskills dimension for companion detection
        companions: dict[str, int] = {}
        for dim_bytes in inner_f.get(2, []):
            if not isinstance(dim_bytes, bytes):
                continue
            df = parse_fields(dim_bytes)
            dim_id = df.get(1, [b""])[0].decode("utf-8") if isinstance(df.get(1, [None])[0], bytes) else ""
            if dim_id != "allskills":
                continue
            for cnt_bytes in df.get(3, []):
                if not isinstance(cnt_bytes, bytes):
                    continue
                cf = parse_fields(cnt_bytes)
                seq_id = cf.get(1, [0])[0]
                count  = cf.get(2, [0])[0]
                if isinstance(seq_id, int) and isinstance(count, int) and seq_id < len(gem_values) and gem_values[seq_id]:
                    companions[gem_values[seq_id]] = count

        return total, companions
    except Exception:
        return 0, {}


def load_secondary_skills() -> set[str]:
    """Load manual secondary skills blocklist from secondary_skills.json."""
    if not os.path.exists(SECONDARY_SKILLS_PATH):
        return set()
    try:
        with open(SECONDARY_SKILLS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        skills = set(data) if isinstance(data, list) else set()
        print(f"  Loaded {len(skills)} manual secondary skills from secondary_skills.json")
        return skills
    except Exception as e:
        print(f"  WARNING: could not load secondary_skills.json: {e}")
        return set()


def run_discovery(
    conn: sqlite3.Connection,
    ascendancies: list[str],
    snapshot: str,
    snapshot_name: str,
    label: str,
    gem_tags: dict[str, list[str]],
    min_builds: int,
    mode: str = 'league_starter',
):
    new_count = skipped_count = 0
    secondary_skills  = load_secondary_skills()
    gem_dict_cache: dict[str, list[str]] = {}  # shared across all queries
    variants = load_variants()

    for asc in ascendancies:
        print(f"\n{'='*60}")
        print(f"  Discovering: {asc}  [mode={mode}]")
        print(f"{'='*60}")

        # Clear existing combos for this ascendancy+mode before re-discovering
        deleted = conn.execute(
            "DELETE FROM combos WHERE ascendancy=? AND mode=?", (asc, mode)
        ).rowcount
        conn.commit()
        if deleted:
            print(f"  Cleared {deleted} existing combo(s) for {asc} [{mode}]")

        skill_counts, all_skill_counts = discover_skills_for_ascendancy(asc, snapshot, snapshot_name, label)
        time.sleep(random.uniform(*DELAY_API_RANGE))

        # Filter: minimum builds + exclude known non-damage skills by name or tag
        valid = []
        for s, c in skill_counts.items():
            if c < min_builds:
                continue
            s_lower = s.lower()
            if s in secondary_skills:
                print(f"  FILTER {s} ({c:,} builds) — manual blocklist")
                continue
            if any(pat in s_lower for pat in NON_DAMAGE_PATTERNS):
                print(f"  FILTER {s} ({c:,} builds) — non-damage name")
                continue
            skill_tags = set(gem_tags.get(s, []))
            if skill_tags & NON_DAMAGE_TAGS:
                # Exceptions: some skills have non-damage tags but are still primary build skills
                if "minion" in skill_tags or "shapeshift" in skill_tags:
                    pass
                else:
                    matched = skill_tags & NON_DAMAGE_TAGS
                    print(f"  FILTER {s} ({c:,} builds) — non-damage tags {matched}")
                    continue
            valid.append((s, c))
        valid.sort(key=lambda x: -x[1])
        print(f"  {len(valid)} damage skills with ≥{min_builds} builds")

        seen_archetypes: dict[tuple, str] = {}             # archetype → first skill name
        # Track EVERY processed skill (queued OR filtered) so the companion check
        # can detect "Ice Nova is a companion of Kelari" even when Kelari was itself
        # filtered (e.g. by primary_ratio or secondary_skills.json) and never queued.
        all_primary_counts: dict[str, int] = {}
        all_allskills:      dict[str, dict[str, int]] = {}

        for skill, count in valid:
            full_tags    = gem_tags.get(skill, [])
            archetype    = get_archetype(skill, full_tags)
            arch_display = f"{archetype[0]}/{archetype[1]}/{archetype[2]}" if archetype else "unknown"

            # Option A: verify this skill is actually used as a primary skill
            time.sleep(random.uniform(*DELAY_API_RANGE))
            primary_count, companions = fetch_primary_data(asc, skill, snapshot, snapshot_name, label, gem_dict_cache)

            # Record EVERY processed skill — needed for companion detection of LATER skills
            all_primary_counts[skill] = primary_count
            all_allskills[skill]      = companions

            if primary_count < MIN_PRIMARY_BUILDS:
                print(f"  FILTER {skill} ({count:,} builds) — only {primary_count} primary builds (support skill)")
                skipped_count += 1
                continue

            primary_ratio = primary_count / count if count else 0
            if primary_ratio < MIN_PRIMARY_RATIO:
                print(f"  FILTER {skill} ({count:,} builds) — low primary ratio {primary_count}/{count} ({primary_ratio:.0%}) — companion spread across builds")
                skipped_count += 1
                continue

            # Companion check — two directions, against ALL previously processed
            # skills (not just queued ones) so a filtered-but-real skill like Kelari
            # can still suppress its dependent skills like Ice Nova:
            #   A) Does this skill appear in >60% of the other skill's primary builds?
            #      Requires the other skill to have meaningful primary count (≥ MIN_PRIMARY_BUILDS).
            #   B) Does the other skill appear in >60% of this skill's primary builds?
            #      Works regardless of the other skill's own primary count.
            companion_of = None
            for other_skill, other_primary in all_primary_counts.items():
                if other_skill == skill:
                    continue
                # Direction A: this skill in other skill's allskills
                pct_a = 0.0
                if other_primary >= MIN_PRIMARY_BUILDS:
                    overlap_a = all_allskills.get(other_skill, {}).get(skill, 0)
                    pct_a     = overlap_a / other_primary * 100

                # Direction B: other skill in this skill's allskills
                overlap_b = companions.get(other_skill, 0)
                pct_b     = overlap_b / primary_count * 100 if primary_count else 0

                if pct_a >= 60 or pct_b >= 60:
                    companion_of = f"{other_skill} (A:{pct_a:.0f}% / B:{pct_b:.0f}%)"
                    break

            if companion_of:
                print(f"  FILTER {skill} ({count:,} builds) — companion skill of {companion_of}")
                skipped_count += 1
                continue

            is_minion = "minion" in set(full_tags)
            if not is_minion and archetype and archetype in seen_archetypes:
                print(f"  SKIP  {skill} ({count:,} builds) — same archetype ({arch_display}) as {seen_archetypes[archetype]}")
                skipped_count += 1
                continue

            if archetype:
                seen_archetypes[archetype] = skill

            print(f"  QUEUE {skill} ({count:,} builds) archetype={arch_display} primary={primary_count}")
            upsert_combo(conn, skill, asc, arch_display, count, mode=mode)
            new_count += 1

            for variant_companion in variants.get(skill, []):
                variant_count = companions.get(variant_companion, 0)
                pct = variant_count / primary_count * 100 if primary_count else 0
                if variant_count < MIN_VARIANT_BUILDS:
                    print(f"  SKIP  {skill} + {variant_companion} ({variant_count:,} builds) — below MIN_VARIANT_BUILDS={MIN_VARIANT_BUILDS}")
                    continue
                print(f"  VARIANT {skill} + {variant_companion} ({variant_count:,} builds, {pct:.0f}% of primary)")
                upsert_combo(conn, skill, asc, arch_display, variant_count, variant_companion, mode=mode)
                new_count += 1

        time.sleep(random.uniform(*DELAY_ASCENDANCY_RANGE))

    # Manual combos — ascendancy-granted skills and other builds poe.ninja won't surface
    manual_combos = load_manual_combos()
    manual_filtered = [m for m in manual_combos if not ascendancies or m["ascendancy"] in ascendancies]
    if manual_filtered:
        # Cache allskills counts per ascendancy to avoid redundant API calls
        asc_skill_counts: dict[str, dict[str, int]] = {}
        for m in manual_filtered:
            skill, asc = m["skill"], m["ascendancy"]
            if asc not in asc_skill_counts:
                time.sleep(random.uniform(*DELAY_API_RANGE))
                _, asc_all = discover_skills_for_ascendancy(asc, snapshot, snapshot_name, label)
                asc_skill_counts[asc] = asc_all  # use allskills for manual — catches ascendancy-granted skills
            count = asc_skill_counts[asc].get(skill, 0)
            print(f"  MANUAL {skill} / {asc} ({count:,} builds)")
            upsert_combo(conn, skill, asc, "manual", count, mode=mode)
            new_count += 1

    print(f"\nDiscovery complete — {new_count} combos queued, {skipped_count} skipped (duplicate tags)")


def discover_exotic_from_db(conn: sqlite3.Connection, ascendancies: list[str] | None = None):
    """
    Derive the exotic-mode queue from existing LS and EG rows in the DB.

    A (skill, ascendancy, variant_companion) tuple qualifies for exotic when
    NEITHER its LS builds_count ≥ POPULAR_LS_THRESHOLD NOR its EG builds_count
    ≥ POPULAR_EG_THRESHOLD. We borrow the larger of the two builds counts and
    the most informative tag_signature so the exotic row is browsable.

    Sequencing: this requires LS and EG discovery+scrape to have already run
    so the DB reflects real per-mode builds_counts. Re-running is idempotent —
    existing exotic rows for matching ascendancies are cleared first.
    """
    targets = set(ascendancies) if ascendancies else None

    rows = conn.execute(
        """
        SELECT skill, ascendancy, variant_companion, mode, builds_count, tag_signature
        FROM combos
        WHERE mode IN ('league_starter', 'endgame')
        """
    ).fetchall()

    # combos[(skill, asc, variant)] = {'league_starter': (count, tag), 'endgame': (count, tag)}
    combos: dict[tuple[str, str, str], dict[str, tuple[int, str]]] = {}
    for r in rows:
        if targets and r["ascendancy"] not in targets:
            continue
        key = (r["skill"], r["ascendancy"], r["variant_companion"] or "")
        combos.setdefault(key, {})[r["mode"]] = (
            r["builds_count"] or 0,
            r["tag_signature"] or "",
        )

    # Clear existing exotic rows for the in-scope ascendancies before re-deriving
    if targets:
        for asc in targets:
            deleted = conn.execute(
                "DELETE FROM combos WHERE ascendancy=? AND mode='exotic'", (asc,)
            ).rowcount
            if deleted:
                print(f"  Cleared {deleted} existing exotic combo(s) for {asc}")
    else:
        deleted = conn.execute("DELETE FROM combos WHERE mode='exotic'").rowcount
        if deleted:
            print(f"  Cleared {deleted} existing exotic combo(s) (all ascendancies)")
    conn.commit()

    queued = skipped = 0
    for (skill, asc, variant), modes in combos.items():
        ls_count, ls_tag = modes.get("league_starter", (0, ""))
        eg_count, eg_tag = modes.get("endgame",        (0, ""))

        if ls_count >= POPULAR_LS_THRESHOLD or eg_count >= POPULAR_EG_THRESHOLD:
            skipped += 1
            continue

        builds_count = max(ls_count, eg_count)
        tag_sig      = ls_tag or eg_tag or ""

        variant_label = f" + {variant}" if variant else ""
        print(f"  QUEUE EXOTIC {skill}{variant_label} / {asc} "
              f"(LS={ls_count}, EG={eg_count} → exotic n={builds_count})")
        upsert_combo(conn, skill, asc, tag_sig, builds_count, variant, mode='exotic')
        queued += 1

    print(f"\nExotic discovery complete — {queued} queued, {skipped} already popular")


# ── Pipeline execution ──────────────────────────────────────────────────────────

# scrape_poeninja.py paces itself with ~5s/character + ~17s/snapshot to dodge poe.ninja
# bot detection. At ~7s/char, 1 hour covers ~500 characters total — enough for any
# single skill on poe.ninja while still bounding a real hang.
STEP_TIMEOUT_DEFAULT = 600
STEP_TIMEOUT_POB     = 3600

def run_step(cmd: list[str], label: str) -> tuple[bool, str]:
    """Run one pipeline step as a subprocess. Returns (success, error_msg)."""
    print(f"  [{label}] {' '.join(cmd)}")
    timeout = STEP_TIMEOUT_POB if label == "pob" else STEP_TIMEOUT_DEFAULT
    try:
        # encoding="utf-8" + errors="replace" — child scripts emit UTF-8, but
        # subprocess defaults to the system codepage on Windows (cp1252) which
        # crashes the reader thread on bytes like 0x8f. replace = no fatal decode.
        result = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "unknown error").strip()[-500:]
            print(f"  [{label}] FAILED (exit {result.returncode})")
            print(f"           {err[:120]}")
            return False, err
        print(f"  [{label}] OK")
        return True, ""
    except subprocess.TimeoutExpired:
        print(f"  [{label}] TIMEOUT after {timeout}s")
        return False, "timeout"
    except Exception as e:
        print(f"  [{label}] ERROR: {e}")
        return False, str(e)


def run_pipeline_for_combo(conn: sqlite3.Connection, skill: str, ascendancy: str,
                           variant_companion: str = '', mode: str = 'league_starter',
                           already_done: dict | None = None):
    """Run the 4-step pipeline for one combo.

    already_done: per-step completion flags from the DB row. When a step is True
    it's skipped (no subprocess, no sleep). Lets an interrupted run pick up at
    the first step that hadn't completed instead of repeating heatmap/pob/etc.
    """
    py = sys.executable
    if mode == 'exotic':
        heatmap_snaps = HEATMAP_SNAPSHOTS_EXOTIC
        pob_snaps     = POB_SNAPSHOTS_EXOTIC
    elif mode == 'endgame':
        heatmap_snaps = HEATMAP_SNAPSHOTS_ENDGAME
        pob_snaps     = POB_SNAPSHOTS_ENDGAME
    else:
        heatmap_snaps = HEATMAP_SNAPSHOTS
        pob_snaps     = POB_SNAPSHOTS
    exp_level = mode  # 'league_starter' | 'endgame' | 'exotic'

    done = already_done or {}

    variant_label = f" + {variant_companion}" if variant_companion else ""
    print(f"\n{'─'*60}")
    print(f"  {skill}{variant_label} / {ascendancy}  [mode={mode}]")
    print(f"{'─'*60}")
    skipped = [k for k, v in done.items() if v]
    if skipped:
        print(f"  Already done: {', '.join(skipped)} (skipping)")

    # Step 1 — Passive heatmap (variants share the base heatmap — no variant flag here)
    if done.get("passives"):
        print("  [heatmap] SKIP (already done)")
    else:
        ok, err = run_step([
            py, "scrape_heatmap.py",
            "--skill", skill,
            "--ascendancy", ascendancy,
            "--snapshots", heatmap_snaps,
            "--experience-level", exp_level,
            "--skip-gems",
        ], "heatmap")
        mark_step(conn, skill, ascendancy, "passives", ok, err, variant_companion, mode)
        if not ok:
            return
        time.sleep(random.uniform(*DELAY_API_RANGE))

    # Step 2 — PoB export scrape
    if done.get("pob"):
        print("  [pob] SKIP (already done)")
    else:
        pob_cmd = [
            py, "scrape_poeninja.py",
            "--skill", skill,
            "--ascendancy", ascendancy,
            "--no-latest",
            "--snapshots", pob_snaps,
            "--append",
        ]
        if variant_companion:
            pob_cmd += ["--variant-skill", variant_companion]
        ok, err = run_step(pob_cmd, "pob")
        mark_step(conn, skill, ascendancy, "pob", ok, err, variant_companion, mode)
        if not ok:
            return
        time.sleep(random.uniform(*DELAY_API_RANGE))

    # Step 3 — Gear analysis
    if done.get("gear"):
        print("  [gear] SKIP (already done)")
    else:
        gear_cmd = [
            py, "analyse_gear.py",
            "--skill", skill,
            "--ascendancy", ascendancy,
            "--experience-level", exp_level,
        ]
        if variant_companion:
            gear_cmd += ["--variant-skill", variant_companion]
        ok, err = run_step(gear_cmd, "gear")
        mark_step(conn, skill, ascendancy, "gear", ok, err, variant_companion, mode)
        if not ok:
            return
        time.sleep(random.uniform(*DELAY_API_RANGE))

    # Step 4 — Gem link analysis
    if done.get("gems"):
        print("  [gems] SKIP (already done)")
    else:
        gems_cmd = [
            py, "analyse_gems.py",
            "--skill", skill,
            "--ascendancy", ascendancy,
            "--experience-level", exp_level,
        ]
        if variant_companion:
            gems_cmd += ["--variant-skill", variant_companion]
        ok, err = run_step(gems_cmd, "gems")
        mark_step(conn, skill, ascendancy, "gems", ok, err, variant_companion, mode)
        if not ok:
            return

    mark_done(conn, skill, ascendancy, variant_companion, mode)
    print(f"  DONE ✓")


# ── Status display ──────────────────────────────────────────────────────────────

def print_status(conn: sqlite3.Connection):
    rows = conn.execute("""
        SELECT ascendancy, skill, variant_companion, mode, builds_count, status,
               passives_done, pob_done, gear_done, gems_done,
               last_scraped, error_msg
        FROM combos
        ORDER BY mode, ascendancy, builds_count DESC
    """).fetchall()

    if not rows:
        print("No combos in database. Run without --resume to discover first.")
        return

    current_asc = None
    current_mode = None
    for r in rows:
        if r["mode"] != current_mode:
            current_mode = r["mode"]
            current_asc  = None
            print(f"\n{'═'*60}")
            print(f"  MODE: {current_mode.upper()}")
            print(f"{'═'*60}")
        if r["ascendancy"] != current_asc:
            current_asc = r["ascendancy"]
            print(f"\n── {current_asc} ──")

        steps = (
            f"P={'✓' if r['passives_done'] else '·'}"
            f" B={'✓' if r['pob_done']     else '·'}"
            f" G={'✓' if r['gear_done']    else '·'}"
            f" M={'✓' if r['gems_done']    else '·'}"
        )
        variant_str = r["variant_companion"]
        skill_display = f"{r['skill']} + {variant_str}" if variant_str else r["skill"]
        err = f"  ← {r['error_msg'][:60]}" if r["error_msg"] else ""
        status = r["status"] or "—"
        builds = r["builds_count"] or 0
        print(f"  [{status:8s}] {steps}  {builds:>6,} builds  {skill_display}{err}")

    total   = len(rows)
    done    = sum(1 for r in rows if r["status"] == "done")
    pending = sum(1 for r in rows if r["status"] == "pending")
    failed  = sum(1 for r in rows if r["status"] == "failed")
    print(f"\nTotal: {total}  Done: {done}  Pending: {pending}  Failed: {failed}")


# ── Audit ───────────────────────────────────────────────────────────────────────

# Newly-released ascendancies don't have early-league PoB import support, so day-2
# and day-3 are legitimately empty on poe.ninja — NOT a scraper failure. The audit
# treats these snapshots as "expected empty" rather than flagging them as missing.
# Update this when GGG releases new ascendancies in future leagues; clear once a
# subsequent league rolls over and the new ascendancy is no longer a fresh release.
PARTIAL_LEAGUE_STARTER_SNAPSHOTS: dict[str, set[str]] = {
    # Druid released with the "fate-of-the-vaal" league start (May 2026)
    "Oracle": {"day-2", "day-3"},
    "Shaman": {"day-2", "day-3"},
}


def _slug_for(skill: str, ascendancy: str, variant_companion: str = '', league: str = 'sc') -> str:
    """Reproduce the slug that scrape_poeninja.py uses for its jsonl filename.

    Routes through util.slug_for_skill so Spectre:/Companion: prefixed skills
    don't break the Windows filesystem via the `:` character.
    """
    from util import slug_for_skill
    asc_slug = ascendancy.lower()
    if variant_companion:
        return f"{slug_for_skill(skill)}_{slug_for_skill(variant_companion)}_{asc_slug}_{league}"
    return f"{slug_for_skill(skill)}_{asc_slug}_{league}"


def audit_pipeline(conn: sqlite3.Connection, fix: bool = False, league: str = 'sc'):
    """
    Audit pob_codes/ jsonl files against expected snapshots per combo.

    A pob scrape can complete with exit 0 but silently skip snapshots that
    returned empty character lists (transient poe.ninja blip, rate-limit, etc).
    This sweep detects combos where the jsonl is missing one or more expected
    snapshots, and optionally flips them back to 'failed' so --resume refetches.

    Heatmap (passives_done) is NOT reset — it's a separate scraper and its data
    doesn't depend on pob completeness.
    """
    import glob
    from collections import Counter

    pob_dir = os.path.join(BASE_DIR, "pob_codes")
    if not os.path.isdir(pob_dir):
        print(f"No pob_codes/ directory at {pob_dir}")
        return

    # Build slug → combo row lookup
    combos_by_slug: dict[str, sqlite3.Row] = {}
    for r in conn.execute(
        "SELECT skill, ascendancy, variant_companion, mode, status, builds_count "
        "FROM combos"
    ).fetchall():
        slug = _slug_for(r["skill"], r["ascendancy"], r["variant_companion"], league)
        combos_by_slug[slug] = r

    ls_expected     = set(POB_SNAPSHOTS.split(","))
    eg_expected     = set(POB_SNAPSHOTS_ENDGAME.split(","))
    exotic_expected = set(POB_SNAPSHOTS_EXOTIC.split(","))

    issues: list[tuple[str, sqlite3.Row, set[str]]] = []
    audited = 0
    print(f"\n{'═'*60}")
    print("  POB JSONL AUDIT")
    print(f"{'═'*60}")
    for path in sorted(glob.glob(os.path.join(pob_dir, "*.jsonl"))):
        if "bak" in path.lower():
            continue
        audited += 1
        slug = os.path.basename(path).replace(".jsonl", "")
        snaps: Counter = Counter()
        total = 0
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    total += 1
                    try:
                        d = json.loads(line)
                        snaps[d.get("snapshot", "?")] += 1
                    except json.JSONDecodeError:
                        pass
        except OSError as e:
            print(f"  {slug}: read error {e}")
            continue

        combo = combos_by_slug.get(slug)
        mode    = combo["mode"]    if combo else "league_starter"
        status  = combo["status"]  if combo else "not-in-db"
        builds  = combo["builds_count"] if combo else None
        ascendancy = combo["ascendancy"] if combo else ""
        if mode == "exotic":
            expected = exotic_expected
        elif mode == "endgame":
            expected = eg_expected
        else:
            expected = ls_expected

        # Subtract snapshots that are legitimately empty for this ascendancy —
        # e.g. newly-released ascendancies during their first league.
        partial_skip: set[str] = set()
        if mode == "league_starter" and ascendancy in PARTIAL_LEAGUE_STARTER_SNAPSHOTS:
            partial_skip = PARTIAL_LEAGUE_STARTER_SNAPSHOTS[ascendancy] & expected
            expected     = expected - partial_skip

        present  = {k for k in snaps if k in expected}
        missing  = expected - present

        snap_str = " ".join(f"{k}={v}" for k, v in sorted(snaps.items()))
        flag = ""
        if missing:
            flag = f"  MISSING {sorted(missing)}"
        elif partial_skip:
            flag = f"  (skipped {sorted(partial_skip)} — new ascendancy)"
        builds_str = f"{builds:>5,}" if isinstance(builds, int) else "  ?  "
        print(f"  [{status:9s}] total={total:4d}  builds={builds_str}  {snap_str}{flag}")
        print(f"             {slug}")
        if missing and combo:
            issues.append((slug, combo, missing))

    print(f"\nAudited: {audited} jsonl file(s)")
    print(f"Combos with missing snapshots: {len(issues)}")

    if not issues:
        return

    if fix:
        for slug, combo, missing in issues:
            conn.execute(
                "UPDATE combos SET status='failed', pob_done=0, gear_done=0, gems_done=0, "
                "error_msg=? "
                "WHERE skill=? AND ascendancy=? AND variant_companion=? AND mode=?",
                (
                    f"audit: missing snapshots {sorted(missing)}",
                    combo["skill"], combo["ascendancy"],
                    combo["variant_companion"], combo["mode"],
                ),
            )
        conn.commit()
        print(f"\n✓ Flipped {len(issues)} combo(s) to 'failed'. "
              f"Run `python run_pipeline.py --resume` to refetch (--append dedupes existing data).")
    else:
        print("\nPass --fix to flip these combos to 'failed' so --resume retries them.")


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PoEProfessor automated data pipeline")
    parser.add_argument("--discover",   action="store_true",
                        help="Discover combos only — save to DB, don't run pipeline steps")
    parser.add_argument("--resume",     action="store_true",
                        help="Skip discovery, only run pending/failed combos")
    parser.add_argument("--status",     action="store_true",
                        help="Print pipeline status table and exit")
    parser.add_argument("--audit",      action="store_true",
                        help="Audit pob_codes/ for combos with missing snapshots and exit")
    parser.add_argument("--fix",        action="store_true",
                        help="With --audit: flip combos with missing snapshots to 'failed' so --resume refetches them")
    parser.add_argument("--ascendancy", help="Only process this ascendancy (e.g. Deadeye)")
    parser.add_argument("--league",     default="sc", choices=["sc", "hc", "ssf", "hcssf"])
    parser.add_argument("--min-builds", type=int, default=MIN_BUILDS,
                        help=f"Min builds for a combo to be scraped (default {MIN_BUILDS})")
    parser.add_argument("--mode",       default="league_starter",
                        choices=["league_starter", "endgame", "exotic"],
                        help="Pipeline mode: league_starter uses day 1-4 snapshots, "
                             "endgame uses week 2-4 snapshots, exotic pools day-4..week-4 "
                             "for sub-meta combos (default: league_starter). "
                             "Exotic derives its queue from existing LS/EG rows — "
                             "LS and EG must complete first.")
    args = parser.parse_args()

    conn = init_db()
    mode = args.mode

    if args.status:
        print_status(conn)
        return

    if args.audit:
        audit_pipeline(conn, fix=args.fix, league=args.league)
        return

    ascendancies = [args.ascendancy] if args.ascendancy else ASCENDANCIES

    # ── Discovery phase ────────────────────────────────────────────────────────
    if not args.resume:
        if mode == "exotic":
            # Exotic derives its queue from existing LS/EG rows rather than
            # re-querying poe.ninja. No snapshot/labels needed.
            print(f"Deriving exotic queue from existing LS/EG combos in {DB_PATH}...")
            discover_exotic_from_db(
                conn,
                ascendancies if args.ascendancy else None,
            )
        else:
            print(f"Getting snapshot info [{args.league.upper()}] mode={mode}...")
            snapshot, snapshot_name, available_labels = get_snapshot(args.league)
            print(f"  Snapshot : {snapshot} ({snapshot_name})")
            print(f"  Available: {sorted(available_labels)}")
            time.sleep(random.uniform(*DELAY_API_RANGE))

            # Use a representative label for discovery — endgame uses week-2/3
            if mode == "endgame":
                preferred = ["week-4", "week-3", "week-2", "week-5", "week-6"]
            else:
                preferred = ["day-4", "day-3", "day-2", "day-1"]
            label = next((l for l in preferred if l in available_labels), "")
            if not label and available_labels:
                label = available_labels[0]
            if not label:
                print("ERROR: no time-machine labels available")
                return
            print(f"  Using label '{label}' for discovery\n")

            # Load gem tags for deduplication (local file — poe.ninja has no PoE2 gem API)
            print("Loading gem tags...")
            gem_tags = load_gem_tags()

            run_discovery(conn, ascendancies, snapshot, snapshot_name, label, gem_tags, args.min_builds, mode)

    if args.discover:
        print("\nDiscovery complete. Run without --discover to start the pipeline.")
        print_status(conn)
        return

    # ── Pipeline phase ─────────────────────────────────────────────────────────
    where  = "status IN ('pending', 'failed') AND mode = ?"
    params: list = [mode]
    if args.ascendancy:
        where += " AND ascendancy = ?"
        params.append(args.ascendancy)

    combos = conn.execute(
        f"SELECT skill, ascendancy, variant_companion, mode, "
        f"passives_done, pob_done, gear_done, gems_done "
        f"FROM combos WHERE {where} ORDER BY builds_count DESC",
        params,
    ).fetchall()

    print(f"\n{len(combos)} combos to process  [mode={mode}]")

    for i, row in enumerate(combos, 1):
        skill, ascendancy, variant_companion = row["skill"], row["ascendancy"], row["variant_companion"]
        already_done = {
            "passives": bool(row["passives_done"]),
            "pob":      bool(row["pob_done"]),
            "gear":     bool(row["gear_done"]),
            "gems":     bool(row["gems_done"]),
        }
        print(f"\n[{i}/{len(combos)}]")
        run_pipeline_for_combo(conn, skill, ascendancy, variant_companion, mode, already_done)
        if i < len(combos):
            if i % LONG_BREAK_EVERY == 0:
                pause = random.uniform(*DELAY_LONG_BREAK_RANGE)
                print(f"\n  [{i}/{len(combos)}] Taking a long break ({pause:.0f}s)...")
                time.sleep(pause)
            else:
                pause = random.uniform(*DELAY_COMBO_RANGE)
                print(f"\n  Waiting {pause:.1f}s before next combo...")
                time.sleep(pause)

    print("\nAll combos processed.")

    # ── Unique item scraping (endgame mode only) ───────────────────────────────
    if mode == 'endgame':
        featured_uniques = load_featured_uniques()
        if featured_uniques:
            print(f"\n{'='*60}")
            print(f"  Unique item scraping ({len(featured_uniques)} featured)")
            print(f"{'='*60}")
            for idx, unique_name in enumerate(featured_uniques):
                print(f"\n  [Unique] {unique_name}")

                ok, err = run_step([
                    py, "scrape_poeninja.py",
                    "--item", unique_name,
                    "--no-latest",
                    "--snapshots", POB_SNAPSHOTS_ENDGAME,
                    "--append",
                ], f"pob")

                if ok:
                    time.sleep(random.uniform(*DELAY_API_RANGE))
                    run_step([
                        py, "analyse_gear.py",
                        "--item", unique_name,
                        "--experience-level", "endgame",
                    ], "gear")
                    time.sleep(random.uniform(*DELAY_API_RANGE))
                    run_step([
                        py, "analyse_gems.py",
                        "--item", unique_name,
                        "--experience-level", "endgame",
                    ], "gems")

                if idx < len(featured_uniques) - 1:
                    pause = random.uniform(*DELAY_COMBO_RANGE)
                    print(f"  Waiting {pause:.1f}s before next unique...")
                    time.sleep(pause)

    print_status(conn)


if __name__ == "__main__":
    main()
