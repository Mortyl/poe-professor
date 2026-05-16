"""
Layered build weights loader.

For a given skill + ascendancy + class, merges weights from:
  1. Class file      — builds/classes/{class}.yaml          (defensive stats)
  2. Tag files       — builds/tags/{tag}.yaml               (one per skill tag)
  3. Ascendancy file — builds/ascendancies/{ascendancy}.yaml (unique nodes, if exists)
  4. Override file   — builds/overrides/{skill}_{ascendancy}.yaml (full override, if exists)

Stat keys appearing in multiple layers take the max value per field,
so overlapping definitions don't artificially inflate scores.
"""

import os
import re
from functools import lru_cache

import yaml

BUILDS_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "builds")

# PoE2 class name → SkillTreeCore.json StartingNodes key
CLASS_START_MAP = {
    "Warrior":   "Marauder",
    "Ranger":    "Ranger",
    "Sorceress": "Witch",
    "Monk":      "Shadow",
    "Mercenary": "Duelist",
    "Huntress":  "Templar",
    "Witch":     "Witch",
    "Druid":     "Templar",
}

# Point caps per experience level
POINT_CAPS = {
    "league_starter": 90,
    "endgame": 123,
}

# Ascendancy point caps per experience level
ASCENDANCY_POINT_CAPS = {
    "league_starter": 6,
    "endgame": 8,
}

# Ascendancy name → SkillTreeCore.json Ascendancy field value
ASCENDANCY_TREE_MAP = {
    # Ranger
    "Deadeye":             "Ranger1",
    "Pathfinder":          "Ranger3",
    # Warrior
    "Warbringer":          "Warrior1",
    "Titan":               "Warrior2",
    "Chieftain":           "Warrior3",
    # Sorceress
    "Stormweaver":         "Sorceress1",
    "Chronomancer":        "Sorceress2",
    # Monk
    "Invoker":             "Monk2",
    "Acolyte of Chayula":  "Monk3",
    # Mercenary
    "Witchhunter":         "Mercenary2",
    "Gemling Legionaire":  "Mercenary3",
    # Witch
    "Bloodmage":           "Witch2",
    # Huntress
    "Amazon":              "Huntress1",
    "Ritualist":           "Huntress3",
    # Druid
    "Wildspeaker":         "Druid1",
    "Warlock":             "Druid2",
}


def _file_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_section(data: dict) -> dict[str, dict]:
    """Flatten offense/defense sections into a single stat key dict."""
    result: dict[str, dict] = {}
    for section in ("offense", "defense"):
        for stat_key, vals in (data.get(section) or {}).items():
            result[stat_key] = {
                "base":    float(vals.get("base", 0.0)),
                "offense": float(vals.get("offense", 0.0)),
                "defense": float(vals.get("defense", 0.0)),
                "boss":    float(vals.get("boss", 1.0)),
                "map":     float(vals.get("map", 1.0)),
            }
    return result


def _merge(base: dict, layer: dict) -> dict:
    """
    Merge layer into base. For existing keys take the max of each field
    so overlapping definitions don't compound.
    """
    result = dict(base)
    for stat_key, vals in layer.items():
        if stat_key not in result:
            result[stat_key] = vals
        else:
            existing = result[stat_key]
            result[stat_key] = {
                "base":    max(existing["base"],    vals["base"]),
                "offense": max(existing["offense"], vals["offense"]),
                "defense": max(existing["defense"], vals["defense"]),
                "boss":    max(existing["boss"],    vals["boss"]),
                "map":     max(existing["map"],     vals["map"]),
            }
    return result


@lru_cache(maxsize=1)
def _load_skill_tags() -> dict[str, list[str]]:
    path = os.path.join(BUILDS_DIR, "skill_tags.yaml")
    return _load_yaml(path)


@lru_cache(maxsize=1)
def load_ascendancy_node_rules() -> dict:
    """
    Load ascendancy_node_rules.yaml.
    Returns dict keyed by tree tag (e.g. "Ranger1") with:
      free_nodes: set of ints (zero-cost junction nodes)
      exclusive_groups: list of frozensets of ints (mutually exclusive choice groups)
    """
    path = os.path.join(BUILDS_DIR, "ascendancy_node_rules.yaml")
    raw = _load_yaml(path)
    result: dict = {}
    for tree_tag, rules in raw.items():
        result[tree_tag] = {
            "free_nodes": set(int(n) for n in (rules.get("free_nodes") or [])),
            "exclusive_groups": [
                frozenset(int(n) for n in group)
                for group in (rules.get("exclusive_groups") or [])
            ],
        }
    return result


@lru_cache(maxsize=64)
def get_weights(skill: str, ascendancy: str, class_name: str) -> dict | None:
    """
    Build merged weights for a skill + ascendancy + class combo.
    Returns None if no weights can be resolved (unknown skill with no tags).
    """
    weights: dict = {}

    # 1. Class defensive weights
    class_path = os.path.join(BUILDS_DIR, "classes", f"{_file_key(class_name)}.yaml")
    weights = _merge(weights, _parse_section(_load_yaml(class_path)))

    # 2. Tag-based offensive weights
    skill_tags = _load_skill_tags()
    tags = skill_tags.get(skill, [])
    for tag in tags:
        tag_path = os.path.join(BUILDS_DIR, "tags", f"{_file_key(tag)}.yaml")
        weights = _merge(weights, _parse_section(_load_yaml(tag_path)))

    # 3. Ascendancy-specific weights
    asc_path = os.path.join(BUILDS_DIR, "ascendancies", f"{_file_key(ascendancy)}.yaml")
    weights = _merge(weights, _parse_section(_load_yaml(asc_path)))

    # 4. Full override (replaces everything if present)
    override_path = os.path.join(BUILDS_DIR, "overrides", f"{_file_key(skill)}_{_file_key(ascendancy)}.yaml")
    if os.path.exists(override_path):
        weights = _parse_section(_load_yaml(override_path))

    return weights or None
