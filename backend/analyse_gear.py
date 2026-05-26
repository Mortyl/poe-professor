"""
analyse_gear.py
---------------
Decodes PoB XML from JSONL files and analyses gear across all builds.

For each equipment slot, reports:
  - Most popular UNIQUE items (name + base type, % of builds using it)
  - Most popular RARE base types (% of builds)
  - Most popular explicit mods on rare/magic items (normalised, % of builds with that slot)

Usage:
  python analyse_gear.py --skill "Lightning Arrow" --ascendancy Deadeye --experience-level league_starter
"""

import os
import re
import json
import base64
import zlib
import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter

POB_DIR    = os.path.join(os.path.dirname(__file__), "pob_codes")
REPORT_DIR = os.path.join(POB_DIR, "reports")

# Which snapshots count for each experience level.
# Endgame intentionally pools day-2..week-6 — that wider range lets us bucket
# by character level inside the report (early-EG lvl 80-95 sourced primarily
# from day-* snapshots, late-EG lvl 96+ from week-* snapshots).
LEAGUE_STARTER_SNAPSHOTS = {"day-1", "day-2", "day-3", "day-4", "day-5", "latest"}
ENDGAME_SNAPSHOTS        = {"day-2", "day-3", "day-4", "day-5", "day-6",
                            "week-1", "week-2", "week-3", "week-4", "week-5", "week-6"}
# Exotic mode pools the wide day-4..week-4 window for low-builds combos
EXOTIC_SNAPSHOTS         = {"day-4", "day-5", "day-6", "week-1", "week-2", "week-3", "week-4"}


def _snapshots_for(experience_level: str) -> set[str]:
    if experience_level == "exotic":
        return EXOTIC_SNAPSHOTS
    if experience_level == "endgame":
        return ENDGAME_SNAPSHOTS
    return LEAGUE_STARTER_SNAPSHOTS


# ── Tier semantics ─────────────────────────────────────────────────────────
# Threshold-based labels we attach to gear / unique items. Saves the frontend
# from re-deriving "is this mandatory or optional" from the raw percentage.
def _tier_label(pct: float) -> str:
    if pct >= 85: return "mandatory"
    if pct >= 50: return "recommended"
    if pct >= 25: return "common"
    return "niche"


# ── Level bucketing (endgame only) ─────────────────────────────────────────
# poe.ninja's top-100-by-level ordering means we never see lvl < ~92, but the
# time-machine returns historical PoBs — so day-* snapshots of the same chars
# give us their lvl 92-95 state. We use level (not snapshot label) as the
# bucket axis because it's the dimension users actually think in.
LEVEL_BUCKETS: list[tuple[str, int, int]] = [
    ("early", 80, 95),   # "just hit maps" cohort
    ("late",  96, 100),  # "fully optimised" cohort
]


def _level_bucket(level: int) -> str | None:
    for name, lo, hi in LEVEL_BUCKETS:
        if lo <= level <= hi:
            return name
    return None


def _get_level(xml_bytes: bytes) -> int:
    """Return character level from a PoB XML, or 0 on failure."""
    try:
        root = ET.fromstring(xml_bytes)
        build = root.find("Build")
        if build is not None:
            return int(build.get("level", 0))
    except Exception:
        pass
    return 0

# Slots we care about — skip swap weapon set and flasks
TARGET_SLOTS = [
    "Weapon 1",
    "Weapon 2",
    "Helmet",
    "Body Armour",
    "Gloves",
    "Boots",
    "Amulet",
    "Ring 1",
    "Ring 2",
    "Belt",
    "Charm 1",
    "Charm 2",
    "Charm 3",
]

# Regex to normalise numeric values in mod lines
_NUM_RANGE = re.compile(r'\d+(\.\d+)?[\-–]\d+(\.\d+)?')  # e.g. 12-34
_NUM       = re.compile(r'\d+(\.\d+)?')                   # e.g. 47

# Extracts the core base type from a magic charm name.
# PoE2 charm bases are always exactly "[Word] Charm" — prefix/suffix sit outside that.
# e.g. "Lustrous Silver Charm of the Sylvan" → "Silver Charm"
#      "Floral Thawing Charm of the Endless" → "Thawing Charm"
#      "Thawing Charm"                        → "Thawing Charm"
_CHARM_BASE_RE = re.compile(r'\b([A-Z][a-z]+ Charm)\b')


def _extract_charm_base(name: str) -> str:
    """Return just the [X] Charm base type from a potentially affix-decorated magic name."""
    m = _CHARM_BASE_RE.search(name)
    return m.group(1) if m else name


# Mods to merge into a single canonical name before counting
_MOD_MERGES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\+#%? to (Fire|Cold|Lightning) Resistance$', re.IGNORECASE),
     "+#% to Elemental Resistance"),
]


def normalise_mod(line: str) -> str:
    """Strip numeric values from a mod line so similar mods collapse together."""
    line = _NUM_RANGE.sub('#', line)
    line = _NUM.sub('#', line)
    line = line.strip()
    for pattern, replacement in _MOD_MERGES:
        if pattern.match(line):
            return replacement
    return line


def decode_pob(code: str) -> bytes | None:
    code = code.strip().replace("-", "+").replace("_", "/")
    pad = 4 - len(code) % 4
    if pad != 4:
        code += "=" * pad
    try:
        return zlib.decompress(base64.b64decode(code))
    except Exception:
        return None


def parse_items(xml_bytes: bytes) -> dict[str, dict]:
    """
    Parse the <Items> section of a PoB XML.
    Returns {slot_name: item_dict} for TARGET_SLOTS.
    item_dict keys: rarity, name, base, mods (list of explicit mod strings)
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return {}

    items_el = root.find("Items")
    if items_el is None:
        return {}

    # Build id → parsed item map
    raw_items: dict[str, dict] = {}
    for item_el in items_el.findall("Item"):
        item_id = item_el.get("id", "0")
        text = (item_el.text or "").strip()
        parsed = _parse_item_text(text)
        if parsed:
            raw_items[item_id] = parsed

    # Build slot_name → item_dict map
    result: dict[str, dict] = {}
    for slot_el in items_el.findall("ItemSet/Slot"):
        slot_name = slot_el.get("name", "")
        item_id   = slot_el.get("itemId", "0")
        if slot_name in TARGET_SLOTS and item_id != "0" and item_id in raw_items:
            result[slot_name] = raw_items[item_id]

    return result


def parse_jewels(xml_bytes: bytes) -> list[dict]:
    """
    Return a list of parsed jewel item dicts socketed in the passive tree.
    Each dict has: rarity, name, base, mods.
    Deduplication within a single build is handled by the caller.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    items_el = root.find("Items")
    if items_el is None:
        return []

    # Build item id → parsed item map (same as parse_items)
    item_map: dict[str, dict] = {}
    for item_el in items_el.findall("Item"):
        item_id = item_el.get("id", "0")
        text = (item_el.text or "").strip()
        parsed = _parse_item_text(text)
        if parsed:
            item_map[item_id] = parsed

    # Find all <Socket nodeId="..." itemId="..."> elements anywhere in the tree
    jewels: list[dict] = []
    for socket_el in root.iter("Socket"):
        item_id = socket_el.get("itemId", "0")
        if item_id != "0" and item_id in item_map:
            jewels.append(item_map[item_id])

    return jewels


def _parse_item_text(text: str) -> dict | None:
    """Parse raw PoB item text block into structured data."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None

    # Line 0: "Rarity: RARE" etc.
    rarity = "NORMAL"
    if lines[0].startswith("Rarity:"):
        rarity = lines[0].split(":", 1)[1].strip().upper()
        lines = lines[1:]

    if not lines:
        return None

    # For UNIQUE and RARE: line 0 = item name, line 1 = base type
    # For NORMAL/MAGIC: line 0 = base type
    if rarity in ("UNIQUE", "RARE"):
        name = lines[0] if len(lines) > 0 else ""
        base = lines[1] if len(lines) > 1 else ""
        lines = lines[2:]
    else:
        name = ""
        base = lines[0] if lines else ""
        lines = lines[1:]

    # Skip metadata lines (key: value patterns, Evasion:, Energy Shield:, etc.)
    # and find Implicits: N to know how many lines to skip as implicits
    num_implicits = 0
    metadata_patterns = re.compile(
        r'^(Unique ID|Item Level|LevelReq|Quality|Evasion|Energy Shield|Armour|'
        r'Ward|Sockets|Rune|Implicits|Charm Slots|Selected Variants|Variant):',
        re.IGNORECASE
    )
    filtered_lines = []
    past_metadata = False
    implicit_countdown = -1

    for line in lines:
        if metadata_patterns.match(line):
            if line.lower().startswith("implicits:"):
                try:
                    num_implicits = int(line.split(":", 1)[1].strip())
                except ValueError:
                    num_implicits = 0
                implicit_countdown = num_implicits
            continue
        # Skip implicit mods
        if implicit_countdown > 0:
            implicit_countdown -= 1
            continue
        filtered_lines.append(line)

    # Filter out enchant/rune/desecrated prefixed mods and ModRange elements
    explicit_mods = []
    for line in filtered_lines:
        if line.startswith("{"):
            # {enchant}, {rune}, {desecrated} — skip
            continue
        if line.startswith("<"):
            # XML elements like <ModRange ...> — skip
            continue
        if not line:
            continue
        explicit_mods.append(line)

    return {
        "rarity": rarity,
        "name":   name,
        "base":   base,
        "mods":   explicit_mods,
    }


def get_life(xml_bytes: bytes) -> float:
    """Return the Life PlayerStat value from a PoB XML. Returns 0 on failure."""
    try:
        root = ET.fromstring(xml_bytes)
        build_el = root.find("Build")
        if build_el is None:
            return 0
        for e in build_el.findall("PlayerStat"):
            if e.get("stat") == "Life":
                return float(e.get("value", 0))
    except Exception:
        pass
    return 0


CHARM_SLOT_NAMES = ["Charm 1", "Charm 2", "Charm 3"]


def _accumulate_slots(xml_list: list[bytes]) -> tuple[dict, dict, dict, dict, Counter, Counter, Counter]:
    """
    Accumulate slot data from a list of decoded PoB XMLs.
    Returns (slot_total, slot_uniques, slot_bases, slot_mods,
             charm_bases_agg, jewel_uniques, jewel_bases).

    charm_bases_agg: per-build set of distinct non-unique charm bases (cross-slot).
    jewel_uniques:   name|base → count for unique jewels.
    jewel_bases:     base → count for non-unique jewels (per-build deduped).
    """
    slot_total:       dict[str, int]     = defaultdict(int)
    slot_uniques:     dict[str, Counter] = defaultdict(Counter)
    slot_bases:       dict[str, Counter] = defaultdict(Counter)
    slot_mods:        dict[str, Counter] = defaultdict(Counter)
    charm_bases_agg:  Counter            = Counter()
    charm_uniques_agg: Counter                   = Counter()  # cross-slot unique charm count
    jewel_uniques:    Counter                    = Counter()
    jewel_bases:      Counter                    = Counter()
    jewel_base_mods:  dict[str, Counter]         = defaultdict(Counter)

    for xml_bytes in xml_list:
        slot_items = parse_items(xml_bytes)
        if not slot_items:
            continue

        # Per-build sets for charm aggregation (avoids double-counting across slots)
        charm_bases_this_build:   set[str] = set()
        charm_uniques_this_build: set[str] = set()  # "name|base" keys

        for slot_name, item in slot_items.items():
            slot_total[slot_name] += 1
            rarity = item["rarity"]
            base   = item["base"]
            name   = item["name"]

            if rarity == "UNIQUE":
                slot_uniques[slot_name][f"{name}|{base}"] += 1
                if slot_name in CHARM_SLOT_NAMES:
                    charm_uniques_this_build.add(f"{name}|{base}")
            else:
                if base:
                    slot_bases[slot_name][base] += 1
                    if slot_name in CHARM_SLOT_NAMES:
                        charm_bases_this_build.add(_extract_charm_base(base))
                seen_mods: set[str] = set()
                for mod in item["mods"]:
                    normalised = normalise_mod(mod)
                    if normalised and normalised not in seen_mods:
                        slot_mods[slot_name][normalised] += 1
                        seen_mods.add(normalised)

        for base in charm_bases_this_build:
            charm_bases_agg[base] += 1
        for key in charm_uniques_this_build:
            charm_uniques_agg[key] += 1

        # Jewels — parse from <Socket> elements, deduplicate within this build
        jewels = parse_jewels(xml_bytes)
        seen_jewel_keys: set[str] = set()
        for jewel in jewels:
            rarity = jewel["rarity"]
            name   = jewel["name"]
            base   = jewel["base"]
            if rarity == "UNIQUE":
                key = f"{name}|{base}"
                if key not in seen_jewel_keys:
                    jewel_uniques[key] += 1
                    seen_jewel_keys.add(key)
            elif base:
                if base not in seen_jewel_keys:
                    jewel_bases[base] += 1
                    seen_jewel_keys.add(base)
                # Track mods per jewel base (normalised, deduplicated per jewel)
                seen_mods: set[str] = set()
                for mod in jewel.get("mods", []):
                    normalised = normalise_mod(mod)
                    if normalised and normalised not in seen_mods:
                        jewel_base_mods[base][normalised] += 1
                        seen_mods.add(normalised)

    return slot_total, slot_uniques, slot_bases, slot_mods, charm_bases_agg, charm_uniques_agg, jewel_uniques, jewel_bases, jewel_base_mods


def _build_slots_out(slot_total, slot_uniques, slot_bases, slot_mods, builds_analysed: int) -> dict:
    """Convert raw counters into the output dict for one build type."""
    slots_out = {}
    for slot in TARGET_SLOTS:
        total = slot_total.get(slot, 0)
        if total == 0:
            continue
        uniques_out = [
            {"name": k.split("|")[0], "base": k.split("|")[1], "count": c,
             "pct": round(c / builds_analysed * 100, 1)}
            for k, c in slot_uniques[slot].most_common(5)
        ]
        bases_out = [
            {"base": b, "count": c, "pct": round(c / total * 100, 1)}
            for b, c in slot_bases[slot].most_common(8)
            if c / total >= 0.03
        ]
        mods_out = [
            {"mod": m, "count": c, "pct": round(c / total * 100, 1)}
            for m, c in slot_mods[slot].most_common(10)
            if c / total >= 0.10
        ]
        slots_out[slot] = {
            "builds_with_slot": total,
            "uniques": uniques_out,
            "rare_bases": bases_out,
            "top_mods": mods_out,
        }
    return slots_out


def _top_uniques_from_slots(slot_uniques, builds_analysed: int) -> list[dict]:
    all_uniques: dict[str, dict] = {}
    for slot in TARGET_SLOTS:
        for key, count in slot_uniques[slot].items():
            name, base = key.split("|", 1)
            if name not in all_uniques or count > all_uniques[name]["count"]:
                pct = round(count / builds_analysed * 100, 1)
                all_uniques[name] = {
                    "name": name, "base": base, "slot": slot,
                    "count": count,
                    "pct": pct,
                    "tier": _tier_label(pct),
                }
    return sorted(all_uniques.values(), key=lambda x: x["count"], reverse=True)[:10]


# ── Signature item detection (co-occurrence) ───────────────────────────────
# "Signature" means the items that define the build's identity, not just the
# top-ranked items per slot. Surfaces three categories:
#   - mandatory: any single unique at >=85% adoption
#   - pairs: two uniques that co-occur in >=50% of builds
#   - trinity: three uniques co-occurring in >=30% of builds
# Identity is via the unique's name (cross-slot — Kalandra's Touch on either
# ring slot collapses to one item).
def _build_unique_sets(xml_list: list[bytes]) -> tuple[list[set[str]], dict[str, str]]:
    """Return per-build sets of unique-item names and a name→base lookup."""
    per_build: list[set[str]] = []
    name_base: dict[str, str] = {}
    for xml_bytes in xml_list:
        names_this_build: set[str] = set()
        # Slot items
        for item in parse_items(xml_bytes).values():
            if item.get("rarity") == "UNIQUE" and item.get("name"):
                n = item["name"]
                names_this_build.add(n)
                if n not in name_base:
                    name_base[n] = item.get("base", "")
        # Jewels
        for jewel in parse_jewels(xml_bytes):
            if jewel.get("rarity") == "UNIQUE" and jewel.get("name"):
                n = jewel["name"]
                names_this_build.add(n)
                if n not in name_base:
                    name_base[n] = jewel.get("base", "")
        if names_this_build:
            per_build.append(names_this_build)
    return per_build, name_base


def _compute_signatures(xml_list: list[bytes]) -> dict:
    """
    Compute signature items: solo (mandatory), pairs, and trinities.

    Returns a dict shaped:
        {"mandatory": [{name, base, pct, tier}, ...],
         "pairs":     [{items: [name, name], joint_pct}, ...],
         "trinity":   [{items: [name, name, name], joint_pct}, ...]}
    """
    n = len(xml_list)
    if n < 20:  # too small to compute meaningful co-occurrence
        return {"mandatory": [], "pairs": [], "trinity": []}

    per_build, name_base = _build_unique_sets(xml_list)
    if not per_build:
        return {"mandatory": [], "pairs": [], "trinity": []}

    # Individual counts
    indiv: Counter = Counter()
    for build in per_build:
        for name in build:
            indiv[name] += 1

    # Mandatory: any unique at >=85% individual usage
    mandatory = []
    for name, c in indiv.most_common():
        pct = round(c / n * 100, 1)
        if pct < 85.0:
            break
        mandatory.append({
            "name": name,
            "base": name_base.get(name, ""),
            "pct":  pct,
            "tier": "mandatory",
        })

    # Candidates for pair/trinity: >=50% individual usage
    candidates = [name for name, c in indiv.items() if c / n >= 0.50]

    # Pair co-occurrence: joint usage >= 50%
    pairs = []
    for i, x in enumerate(candidates):
        for y in candidates[i+1:]:
            joint = sum(1 for build in per_build if x in build and y in build)
            joint_pct = round(joint / n * 100, 1)
            if joint_pct >= 50.0:
                pairs.append({
                    "items":     sorted([x, y]),
                    "joint_pct": joint_pct,
                })
    pairs.sort(key=lambda p: -p["joint_pct"])

    # Trinity co-occurrence: joint usage >= 30%
    trinities = []
    for i, x in enumerate(candidates):
        for j in range(i + 1, len(candidates)):
            y = candidates[j]
            for k in range(j + 1, len(candidates)):
                z = candidates[k]
                joint = sum(1 for build in per_build if x in build and y in build and z in build)
                joint_pct = round(joint / n * 100, 1)
                if joint_pct >= 30.0:
                    trinities.append({
                        "items":     sorted([x, y, z]),
                        "joint_pct": joint_pct,
                    })
    trinities.sort(key=lambda t: -t["joint_pct"])

    return {
        "mandatory": mandatory[:5],
        "pairs":     pairs[:10],
        "trinity":   trinities[:5],
    }


def _apply_tiers_to_list(items: list[dict]) -> list[dict]:
    """Stamp a 'tier' field onto each item dict based on its 'pct'."""
    for item in items:
        if "pct" in item and "tier" not in item:
            item["tier"] = _tier_label(item["pct"])
    return items


def _build_section(xml_list: list[bytes]) -> dict:
    """Build one section dict (life or es, or a level-bucketed slice) from XMLs."""
    n = len(xml_list)
    st, su, sb, sm, cb_agg, cu_agg, ju, jb, jbm = _accumulate_slots(xml_list)
    slots_out   = _build_slots_out(st, su, sb, sm, n)
    top_uniques = _top_uniques_from_slots(su, n)

    charm_bases_out = _apply_tiers_to_list([
        {"base": b, "count": c, "pct": round(c / n * 100, 1)}
        for b, c in cb_agg.most_common(10)
    ])
    charm_uniques_out = _apply_tiers_to_list([
        {"name": k.split("|")[0], "base": k.split("|")[1], "count": c,
         "pct": round(c / n * 100, 1)}
        for k, c in cu_agg.most_common(10)
    ])
    jewel_uniques_out = _apply_tiers_to_list([
        {"name": k.split("|")[0], "base": k.split("|")[1], "count": c,
         "pct": round(c / n * 100, 1)}
        for k, c in ju.most_common(10)
    ])
    jewel_bases_out = _apply_tiers_to_list([
        {
            "base":     b,
            "count":    c,
            "pct":      round(c / n * 100, 1),
            "top_mods": [mod for mod, _ in jbm[b].most_common(3)],
        }
        for b, c in jb.most_common(10)
    ])

    return {
        "builds_analysed":  n,
        "top_uniques":      top_uniques,
        "charm_bases":      charm_bases_out,
        "charm_uniques":    charm_uniques_out,
        "jewel_uniques":    jewel_uniques_out,
        "jewel_bases":      jewel_bases_out,
        "slots":            slots_out,
        "signature_items":  _compute_signatures(xml_list),
    }


def analyse(skill: str, ascendancy: str, experience_level: str,
            variant_skill: str = '', item: str = '') -> dict:
    """
    Main analysis — returns the full gear report dict, split by life vs ES.
    Pass item= to analyse builds scraped by unique item (scrape_poeninja --item).
    """
    from util import slug_for_skill
    if item:
        slug = f"{slug_for_skill(item)}_"
    elif variant_skill:
        slug = f"{slug_for_skill(skill)}_{slug_for_skill(variant_skill)}_{ascendancy.lower()}_"
    else:
        slug = f"{slug_for_skill(skill)}_{ascendancy.lower()}_"
    snapshots = _snapshots_for(experience_level)

    # Load all matching JSONL entries
    entries = []
    for fname in os.listdir(POB_DIR):
        if not (fname.endswith(".jsonl") and slug in fname.lower()):
            continue
        with open(os.path.join(POB_DIR, fname), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item:
                    # Item-scraped files already contain only the right snapshots —
                    # include all entries regardless of snapshot label
                    entries.append(obj)
                elif obj.get("snapshot", "latest") in snapshots:
                    entries.append(obj)

    label = item if item else f"{skill} / {ascendancy}"
    print(f"Loading [{experience_level}] builds for {label}...")
    print(f"  {len(entries)} raw entries found in JSONL files")

    # Decode each PoB once and capture (xml, life, level) tuples so we can
    # partition by life-vs-ES AND by level bucket without re-parsing.
    parsed: list[tuple[bytes, float, int]] = []
    for entry in entries:
        xml_bytes = decode_pob(entry["code"])
        if not xml_bytes:
            continue
        parsed.append((xml_bytes, get_life(xml_bytes), _get_level(xml_bytes)))

    life_xmls = [x for x, lf, _ in parsed if lf > 1]
    es_xmls   = [x for x, lf, _ in parsed if lf <= 1]
    print(f"  Life builds: {len(life_xmls)}  |  ES builds: {len(es_xmls)}\n")

    # ── Legacy life/es sections (combined across all levels) ─────────────
    results: dict[str, dict] = {}
    for build_type, xml_list in [("life", life_xmls), ("es", es_xmls)]:
        if not xml_list:
            continue
        section = _build_section(xml_list)
        results[build_type] = section

        # Console summary
        print(f"=== {build_type.upper()} BUILDS ({len(xml_list)}) ===")
        print("--- TOP UNIQUES ---")
        for u in section["top_uniques"][:5]:
            print(f"  {u['pct']:5.1f}%  [{u['tier']:11s}] {u['name']} ({u['base']}) [{u['slot']}]")
        sigs = section["signature_items"]
        if sigs["mandatory"]:
            print("--- MANDATORY ---")
            for m in sigs["mandatory"]:
                print(f"  {m['pct']:5.1f}%  {m['name']}")
        if sigs["pairs"]:
            print("--- SIGNATURE PAIRS ---")
            for p in sigs["pairs"][:3]:
                print(f"  {p['joint_pct']:5.1f}%  {' + '.join(p['items'])}")
        if sigs["trinity"]:
            print("--- SIGNATURE TRINITY ---")
            for t in sigs["trinity"][:3]:
                print(f"  {t['joint_pct']:5.1f}%  {' + '.join(t['items'])}")
        print()

    # ── Level-bucketed sections (endgame only) ──────────────────────────
    # poe.ninja's leaderboard skews high, so this only produces meaningful
    # split for endgame mode where we have day-* + week-* snapshot diversity.
    level_buckets: dict[str, dict] = {}
    if experience_level == "endgame":
        for bucket_name, lo, hi in LEVEL_BUCKETS:
            b_life = [x for x, lf, lvl in parsed if lf >  1 and lo <= lvl <= hi]
            b_es   = [x for x, lf, lvl in parsed if lf <= 1 and lo <= lvl <= hi]
            if not (b_life or b_es):
                continue
            bucket: dict = {
                "level_range":     f"{lo}-{hi}" if hi < 100 else f"{lo}+",
                "builds_analysed": len(b_life) + len(b_es),
            }
            # Only emit life/es sub-sections when there's enough data (min 20)
            # to make signatures and percentages trustworthy.
            if len(b_life) >= 20:
                bucket["life"] = _build_section(b_life)
            if len(b_es)   >= 20:
                bucket["es"]   = _build_section(b_es)
            # Skip empty buckets (no life or es side reached threshold)
            if "life" in bucket or "es" in bucket:
                level_buckets[bucket_name] = bucket

        if level_buckets:
            print("=== LEVEL BUCKETS ===")
            for name, b in level_buckets.items():
                pieces = []
                if "life" in b: pieces.append(f"life={b['life']['builds_analysed']}")
                if "es"   in b: pieces.append(f"es={b['es']['builds_analysed']}")
                print(f"  {name:6s} (lvl {b['level_range']:6s}) n={b['builds_analysed']}  ({', '.join(pieces)})")
            print()

    report = {
        "skill":            item if item else skill,
        "ascendancy":       "Any" if item else ascendancy,
        "experience_level": experience_level,
        "builds_analysed":  len(life_xmls) + len(es_xmls),
        "life":             results.get("life", {}),
        "es":               results.get("es", {}),
        "level_buckets":    level_buckets or None,
    }
    if item:
        report["item"] = item  # extra field so consumers can detect item-mode reports

    os.makedirs(REPORT_DIR, exist_ok=True)
    # Filename includes the ascendancy (and variant) so different ascendancies playing
    # the same skill don't overwrite each other's report.
    from util import slug_for_skill
    asc_slug = ascendancy.lower()
    if item:
        out_path = os.path.join(REPORT_DIR, f"{slug_for_skill(item)}_{experience_level}_gear.json")
    elif variant_skill:
        out_path = os.path.join(REPORT_DIR, f"{slug_for_skill(skill)}_{slug_for_skill(variant_skill)}_{asc_slug}_{experience_level}_gear.json")
    else:
        out_path = os.path.join(REPORT_DIR, f"{slug_for_skill(skill)}_{asc_slug}_{experience_level}_gear.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Gear report: {out_path}")
    return report


def discover_slots(skill: str, ascendancy: str, experience_level: str, variant_skill: str = '') -> None:
    """Print every unique slot name found in the JSONL data, searching all XML paths."""
    from util import slug_for_skill
    if variant_skill:
        slug = f"{slug_for_skill(skill)}_{slug_for_skill(variant_skill)}_{ascendancy.lower()}_"
    else:
        slug = f"{slug_for_skill(skill)}_{ascendancy.lower()}_"
    snapshots = _snapshots_for(experience_level)

    all_slots: Counter = Counter()
    xml_paths_seen: set[str] = set()
    builds_checked = 0

    for fname in os.listdir(POB_DIR):
        if not (fname.endswith(".jsonl") and slug in fname.lower()):
            continue
        with open(os.path.join(POB_DIR, fname), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("snapshot", "latest") not in snapshots:
                    continue
                xml_bytes = decode_pob(obj["code"])
                if not xml_bytes:
                    continue
                try:
                    root = ET.fromstring(xml_bytes)
                except ET.ParseError:
                    continue

                # Named slots (gear, charms, flasks)
                for el in root.iter():
                    if el.get("itemId") and el.get("itemId") != "0":
                        name = el.get("name", "")
                        xml_paths_seen.add(el.tag)
                        if name:
                            all_slots[name] += 1
                        else:
                            # Un-named element with an itemId — could be jewels
                            # Print tag + all attributes for inspection
                            all_slots[f"<{el.tag} {dict(el.attrib)}>"] += 1

                builds_checked += 1

    print(f"\nAll slotted items found across {builds_checked} builds ({experience_level}):\n")
    for slot_name, count in sorted(all_slots.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}x  {slot_name!r}")
    print(f"\nElement tags containing slotted items: {sorted(xml_paths_seen)}")


def main():
    parser = argparse.ArgumentParser(description="Analyse gear from PoB JSONL files")
    parser.add_argument("--skill",             default="Lightning Arrow")
    parser.add_argument("--ascendancy",        default="Deadeye")
    parser.add_argument("--item",              default="",
                        help="Unique item name — analyse builds scraped with --item. "
                             "Overrides --skill/--ascendancy.")
    parser.add_argument("--experience-level",  default="league_starter",
                        choices=["league_starter", "endgame", "exotic"])
    parser.add_argument("--discover",          action="store_true",
                        help="Print all slot names found in data without running full analysis")
    parser.add_argument("--variant-skill",     default="",
                        help="If set, read JSONL files for this variant and include variant slug in output filename.")
    args = parser.parse_args()

    if args.discover:
        discover_slots(args.skill, args.ascendancy, args.experience_level, args.variant_skill)
    else:
        analyse(args.skill, args.ascendancy, args.experience_level, args.variant_skill, args.item)


if __name__ == "__main__":
    main()
