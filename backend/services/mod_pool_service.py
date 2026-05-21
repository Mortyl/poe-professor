"""Mod-pool service backed by RePoE2 data.

Loads three JSON files from `backend/data/repoe2/`:
  - mods.json          — full mod metadata (14k entries, ~11 MB)
  - base_items.json    — base-item definitions (4k entries, ~6 MB)
  - mods_by_base.json  — class → tag-signature → {bases, mods{prefix|suffix|corrupted: {group: {mod_id: unlock_ilvl}}}}

The data is loaded lazily on first access and cached in module-level globals
for the lifetime of the process. ~19 MB resident; trivial for a backend.

Source: https://github.com/SilkroadLabs/rePoE2 (last update Dec 2025).
Refresh manually per major PoE2 patch by re-downloading the three files.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "repoe2")
MODS_PATH = os.path.join(DATA_DIR, "mods.json")
BASES_PATH = os.path.join(DATA_DIR, "base_items.json")
MODS_BY_BASE_PATH = os.path.join(DATA_DIR, "mods_by_base.json")


# ── Lazy loaders ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_mods() -> dict:
    with open(MODS_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_bases() -> dict:
    with open(BASES_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_mods_by_base() -> dict:
    with open(MODS_BY_BASE_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── Public API ─────────────────────────────────────────────────────────────

@dataclass
class ModInfo:
    """Light projection of a mod row — what the frontend selector needs."""
    id: str
    name: str
    group: str                 # e.g. "Life", "FireResistance"
    generation_type: str       # "prefix" | "suffix" | "corrupted" | ...
    required_level: int        # minimum ilvl for ANY tier of this mod_id
    unlock_ilvl: int           # minimum ilvl for THIS specific tier on the base
    text: str                  # display string from RePoE2 (with ranges)


def _normalize_class_lookup(item_class: str, classes: dict) -> str | None:
    """RePoE2 keys are inconsistent (singular vs plural). Try a few variants."""
    if item_class in classes:
        return item_class
    # Try plural
    if (item_class + "s") in classes:
        return item_class + "s"
    # Try without trailing 's' (in case caller passed plural)
    if item_class.endswith("s") and item_class[:-1] in classes:
        return item_class[:-1]
    # Case-insensitive fallback
    lower = item_class.lower()
    for k in classes:
        if k.lower() == lower or k.lower() == lower + "s":
            return k
    return None


def _matches_base_name(base_name: str, base_metadata_id: str, bases: dict) -> bool:
    """A `bases` entry is a metadata id like 'Metadata/Items/Amulets/FourAmulet1'.
    We need to match it against a human-readable base name (e.g. 'Crimson Amulet').
    Resolve the metadata id → human name via base_items.json."""
    entry = bases.get(base_metadata_id)
    if not entry:
        return False
    return entry.get("name", "").lower() == base_name.lower()


def is_rollable(
    item_class: str,
    mod_id: str,
    ilvl: int,
    base_name: str | None = None,
) -> bool:
    """Return True if mod `mod_id` can roll on an item with the given class +
    ilvl (optionally narrowed to a specific base). False on any mismatch."""
    mods_by_base = _load_mods_by_base()
    class_key = _normalize_class_lookup(item_class, mods_by_base)
    if class_key is None:
        return False

    bases = _load_bases() if base_name else None
    class_data = mods_by_base[class_key]

    for sig_data in class_data.values():
        # If base_name supplied, only consider signatures that contain this base
        if base_name is not None:
            if not any(_matches_base_name(base_name, b, bases) for b in sig_data.get("bases", [])):
                continue

        for groups in sig_data.get("mods", {}).values():
            for mods in groups.values():
                unlock = mods.get(mod_id)
                if unlock is not None:
                    return ilvl >= unlock
    return False


def rollable_mods_for(
    item_class: str,
    ilvl: int,
    base_name: str | None = None,
) -> dict[str, dict[str, list[ModInfo]]]:
    """Return all mods that can roll on this item, grouped by:

        { generation_type: { group_name: [ModInfo, ModInfo, ...] } }

    e.g.
        {
          "prefix": { "Life": [Life1, Life2, Life3], "PhysicalDamage": [...] },
          "suffix": { "Strength": [...], "FireResistance": [...] },
        }

    Tiers above the item's ilvl are EXCLUDED. The frontend mod-by-mod selector
    consumes this directly: groups become collapsible families, mods within a
    group are the rollable tiers.
    """
    mods_by_base = _load_mods_by_base()
    mods_meta = _load_mods()
    bases = _load_bases() if base_name else None

    class_key = _normalize_class_lookup(item_class, mods_by_base)
    if class_key is None:
        return {}

    # Body Armours / other multi-base classes have many tag signatures
    # (str_armour, dex_armour, int_armour, ...). The same mod_id often
    # appears in several sigs — dedupe by mod_id keeping the lowest
    # unlock_ilvl seen across signatures.
    # Structure: { gen_type: { group: { mod_id: ModInfo } } }
    accumulator: dict[str, dict[str, dict[str, ModInfo]]] = {}

    for sig_data in mods_by_base[class_key].values():
        if base_name is not None:
            if not any(_matches_base_name(base_name, b, bases) for b in sig_data.get("bases", [])):
                continue

        for gen_type, groups in sig_data.get("mods", {}).items():
            gen_bucket = accumulator.setdefault(gen_type, {})
            for group_name, mods in groups.items():
                group_bucket = gen_bucket.setdefault(group_name, {})
                for mod_id, unlock_ilvl in mods.items():
                    if ilvl < unlock_ilvl:
                        continue
                    existing = group_bucket.get(mod_id)
                    if existing is not None and existing.unlock_ilvl <= unlock_ilvl:
                        continue  # already have a same-or-easier unlock
                    meta = mods_meta.get(mod_id, {})
                    group_bucket[mod_id] = ModInfo(
                        id=mod_id,
                        name=meta.get("name", ""),
                        group=group_name,
                        generation_type=gen_type,
                        required_level=int(meta.get("required_level", 0) or 0),
                        unlock_ilvl=int(unlock_ilvl),
                        text=meta.get("text", ""),
                    )

    # Project the deduped accumulator back to the public shape, sorting
    # each group's mods by unlock_ilvl ascending (tier 1 → tier N).
    out: dict[str, dict[str, list[ModInfo]]] = {}
    for gen_type, gen_bucket in accumulator.items():
        out[gen_type] = {
            group: sorted(by_id.values(), key=lambda m: m.unlock_ilvl)
            for group, by_id in gen_bucket.items()
        }
    return out


def known_item_classes() -> list[str]:
    """All item classes RePoE2 has data for. Useful for debugging /
    validation that an incoming item.class isn't a typo. The empty-string
    key (used by RePoE2 for items without a class) is filtered out."""
    return [k for k in _load_mods_by_base().keys() if k]


def base_name_for_metadata_id(metadata_id: str) -> str:
    """e.g. 'Metadata/Items/Amulets/FourAmulet1' → 'Crimson Amulet'.
    Empty string if not found."""
    return _load_bases().get(metadata_id, {}).get("name", "")
