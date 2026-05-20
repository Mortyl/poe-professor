import json
import os
import sqlite3
from fastapi import APIRouter, HTTPException, Query
from models.schemas import BuildRequest, BuildGuide
from services.build_service import generate_build

router = APIRouter()

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "pipeline.db")
GEM_TAGS_PATH = os.path.join(BASE_DIR, "gem_tags.json")
ARCHETYPE_CONFIG_PATH = os.path.join(BASE_DIR, "archetype_config.json")
FEATURED_UNIQUES_PATH = os.path.join(BASE_DIR, "featured_uniques.json")
UNIQUE_DRIVEN_PATH    = os.path.join(BASE_DIR, "unique_driven_builds.json")
GEAR_REPORT_DIR = os.path.join(BASE_DIR, "pob_codes", "reports")


# ── Archetype assignment ───────────────────────────────────────────────────

def _load_gem_tags() -> dict:
    if not os.path.exists(GEM_TAGS_PATH):
        return {}
    with open(GEM_TAGS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_archetype_config() -> dict:
    with open(ARCHETYPE_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_featured_uniques() -> list[str]:
    """Load the list of unique item names to feature, from featured_uniques.json."""
    if not os.path.exists(FEATURED_UNIQUES_PATH):
        return []
    try:
        with open(FEATURED_UNIQUES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return [u.strip() for u in data if isinstance(u, str) and u.strip()]
    except Exception:
        return []


def _load_unique_driven_builds() -> list[dict]:
    """Load skill→unique mappings from unique_driven_builds.json.

    Each entry is: {"skill": str, "unique": str, "ascendancies": [str, ...]}
    Empty/missing ascendancies list = applies to every ascendancy.
    """
    if not os.path.exists(UNIQUE_DRIVEN_PATH):
        return []
    try:
        with open(UNIQUE_DRIVEN_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [
            e for e in data
            if isinstance(e, dict) and isinstance(e.get("skill"), str) and isinstance(e.get("unique"), str)
        ]
    except Exception:
        return []


def _unique_driven_match(skill: str, ascendancy: str, mappings: list[dict]) -> str | None:
    """Return the unique item name if this combo is unique-driven, else None."""
    for entry in mappings:
        if entry["skill"] != skill:
            continue
        ascendancies = entry.get("ascendancies") or []
        if not ascendancies or ascendancy in ascendancies:
            return entry["unique"]
    return None


def _build_unique_subs(mode: str, routed: dict | None = None) -> list[dict]:
    """
    Build the subs for the Unique archetype from two sources:

    1. `featured_uniques.json` — standalone unique builds (Mjolner, Headhunter, …)
       backed by a gear report scraped via `scrape_poeninja.py --item ...`.

    2. `routed` — combos from the main DB that `_assign_archetype` routed here
       because their skill is unique-driven (e.g. His Scattering Calamity → The
       Unborn Lich). Keys are the unique item names; values are lists of build
       entries already shaped like the rest of the browse payload.

    The two sources merge: if a unique appears in BOTH (a featured standalone
    entry AND skill-routed combos), all the skill combos surface as additional
    builds under the same sub.
    """
    featured = _load_featured_uniques()
    routed   = routed or {}
    subs: list[dict] = []
    seen: dict[str, dict] = {}  # unique_name → sub object

    # Pass 1 — featured standalone uniques (existing behaviour)
    for unique_name in featured:
        item_slug = unique_name.lower().replace(" ", "_").replace("'", "").replace(",", "")
        report_path = os.path.join(GEAR_REPORT_DIR, f"{item_slug}_{mode}_gear.json")

        builds_analysed = 0
        scraped = False
        if os.path.exists(report_path):
            try:
                with open(report_path, encoding="utf-8") as f:
                    report = json.load(f)
                builds_analysed = report.get("builds_analysed", 0)
                scraped = True
            except Exception:
                pass

        sub = {
            "id": item_slug,
            "label": unique_name,
            "builds": [{
                "skill":             unique_name,
                "ascendancy":        "Any",
                "builds_count":      builds_analysed,
                "variant_companion": "",
                "tag_signature":     f"unique/{unique_name}",
                "scraped":           scraped,
            }],
            "total":   builds_analysed,
            "subsubs": None,
        }
        subs.append(sub)
        seen[unique_name] = sub

    # Pass 2 — skill-driven combos routed here from the main DB.
    # Either merge into an existing featured sub, or create a new sub for this unique.
    for unique_name, builds in routed.items():
        if not builds:
            continue
        if unique_name in seen:
            sub = seen[unique_name]
            sub["builds"].extend(builds)
            sub["total"] += sum(b["builds_count"] for b in builds)
        else:
            item_slug = unique_name.lower().replace(" ", "_").replace("'", "").replace(",", "")
            new_sub = {
                "id": item_slug,
                "label": unique_name,
                "builds": list(builds),
                "total":  sum(b["builds_count"] for b in builds),
                "subsubs": None,
            }
            subs.append(new_sub)
            seen[unique_name] = new_sub

    return subs


def _assign_archetype(skill: str, tag_sig: str, variant_companion: str, gem_tags: dict, config: dict,
                      ascendancy: str = "", unique_driven: list[dict] | None = None):
    """
    Returns (archetype_id, sub_id | None).
    Priority: unique-driven → minion → shapeshifter → ranged → spell → melee → trigger → other

    Unique-driven skills (e.g. His Scattering Calamity / Titan, which only really
    exists as a build because of The Unborn Lich) are routed to the 'unique'
    archetype. The sub_id is the unique item NAME (not slug) — _build_unique_subs
    uses it as a dict key to merge with featured uniques.
    """
    # ── Unique-driven check (first, takes precedence over normal routing) ──
    if unique_driven:
        u = _unique_driven_match(skill, ascendancy, unique_driven)
        if u:
            return ("unique", u)

    parts = (tag_sig or "").split("/")
    source = parts[0] if len(parts) > 0 else "other"
    delivery = parts[1] if len(parts) > 1 else "other"
    damage = parts[2] if len(parts) > 2 else "none"

    skill_tags = set(gem_tags.get(skill, []))

    # Spectre/Companion prefix → always minion regardless of gem_tags
    if skill.startswith(("Spectre:", "Companion:")):
        return ("minion", None)

    # Shapeshifter: delivery-based — check BEFORE minion to handle dual-tagged skills like Pounce
    shapeshift_deliveries = {"werewolf", "wyvern", "bear"}
    if delivery in shapeshift_deliveries:
        shapeshifter_arch = next((a for a in config["archetypes"] if a["id"] == "shapeshifter"), {})
        sub = _match_sub(shapeshifter_arch, delivery=delivery)
        return ("shapeshifter", sub)

    # Minion check (gem tag)
    if "minion" in skill_tags:
        return ("minion", None)

    # Ranged: bow or crossbow/grenade
    if source == "attack" and delivery == "bow":
        return ("ranged", _assign_bow_sub(damage))

    if source == "attack" and delivery in {"crossbow", "grenade"}:
        sub = _assign_crossbow_sub(skill, gem_tags)
        return ("ranged", sub)

    # Spell: source only, sub by damage type
    if source == "spell":
        spell_arch = next((a for a in config["archetypes"] if a["id"] == "spell"), {})
        sub = _match_sub(spell_arch, damage=damage)
        return ("spell", sub)

    # Melee: any remaining attack, including totem attacks
    if source in ("attack", "other") and source != "spell":
        sub = _assign_melee_sub(skill, delivery, ascendancy=ascendancy, gem_tags=gem_tags)
        return ("melee", sub)

    # Trigger: variant builds
    if variant_companion:
        return ("trigger", None)

    return ("other", None)


def _match_sub(arch: dict, delivery: str = "", damage: str = "") -> str | None:
    for sub in arch.get("sub", []):
        if delivery and delivery in sub.get("delivery", []):
            return sub["id"]
        if damage and damage in sub.get("damage", []):
            return sub["id"]
    return None


# Delivery → melee sub
_DELIVERY_TO_MELEE_SUB: dict[str, str] = {
    "mace":         "twohanded_mace",
    "flail":        "twohanded_mace",
    "quarterstaff": "quarterstaff",
    "staff":        "quarterstaff",
    "spear":        "spear",
    "sword":        "one_shield",
    "axe":          "one_shield",
    "claw":         "one_shield",
    "dagger":       "one_shield",
    "sceptre":      "one_shield",
    "wand":         "one_shield",
}

# Gem tag → melee sub (for generic 'melee' delivery)
_GEM_TAG_TO_MELEE_SUB: dict[str, str] = {
    "mace":         "twohanded_mace",
    "flail":        "twohanded_mace",
    "quarterstaff": "quarterstaff",
    "staff":        "quarterstaff",
    "spear":        "spear",
    "sword":        "one_shield",
    "axe":          "one_shield",
    "claw":         "one_shield",
    "dagger":       "one_shield",
    "sceptre":      "one_shield",
    "wand":         "one_shield",
}

# Ascendancy fallback when delivery/gem tags give no signal
_ASCENDANCY_MELEE_SUB: dict[str, str] = {
    "Titan":              "twohanded_mace",
    "Warbringer":         "one_shield",
    "Invoker":            "quarterstaff",
    "Acolyte of Chayula": "quarterstaff",
    "Amazon":             "spear",
    "Spirit Walker":      "spear",
    "Witchhunter":        "one_shield",
    "Tactician":          "one_shield",
    "Gemling Legionnaire":"one_shield",
    "Blood Mage":         "one_shield",
    "Pathfinder":         "one_shield",
    "Deadeye":            "one_shield",
}


def _assign_bow_sub(damage: str) -> str:
    if damage == "lightning":
        return "bow_lightning"
    if damage == "cold":
        return "bow_cold"
    if damage in ("chaos", "physical"):
        return "bow_poison"
    return "bow_lightning"  # fallback


def _assign_crossbow_sub(skill: str, gem_tags: dict) -> str:
    """Split crossbow builds: grenade tag → grenades, ammunition tag → ammo, else → ammo (fallback)."""
    skill_tags = set(gem_tags.get(skill, []))
    if "grenade" in skill_tags:
        return "grenades"
    if "ammunition" in skill_tags:
        return "ammo"
    return "ammo"


def _assign_melee_sub(skill: str, delivery: str, ascendancy: str, gem_tags: dict) -> str:
    # 1. Direct delivery match
    if delivery in _DELIVERY_TO_MELEE_SUB:
        return _DELIVERY_TO_MELEE_SUB[delivery]

    # 2. Gem tag match (handles generic 'melee' delivery)
    skill_tags = gem_tags.get(skill, [])
    for tag in skill_tags:
        if tag in _GEM_TAG_TO_MELEE_SUB:
            return _GEM_TAG_TO_MELEE_SUB[tag]

    # 3. Ascendancy-based fallback
    if ascendancy in _ASCENDANCY_MELEE_SUB:
        return _ASCENDANCY_MELEE_SUB[ascendancy]

    return "one_shield"  # generic fallback


# ── Browse endpoint ────────────────────────────────────────────────────────

@router.get("/browse")
async def browse_builds(mode: str = Query(default="endgame", pattern="^(league_starter|endgame|exotic)$")):
    """
    Return all scraped builds grouped by archetype.
    mode: 'league_starter' | 'endgame' | 'exotic'  (controls which archetypes are visible)
    """
    if not os.path.exists(DB_PATH):
        return {"archetypes": [], "total": 0}

    config = _load_archetype_config()
    gem_tags = _load_gem_tags()

    # Load visible archetypes for this mode
    visible = {a["id"] for a in config["archetypes"] if mode in a.get("modes", [])}

    # Query combos for this mode.
    # If the DB was created before the mode column was added (migration pending),
    # fall back to an unfiltered query so the browse still works.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Check whether the mode column exists yet
        has_mode_col = any(
            row[1] == "mode"
            for row in conn.execute("PRAGMA table_info(combos)").fetchall()
        )

        if has_mode_col:
            rows = conn.execute(
                """
                SELECT skill, ascendancy, tag_signature, builds_count, variant_companion,
                       pob_done, gear_done, gems_done
                FROM combos
                WHERE builds_count > 0
                  AND mode = ?
                ORDER BY builds_count DESC
                """,
                (mode,),
            ).fetchall()
            # If endgame has no data yet, fall back to league_starter combos
            if not rows and mode == "endgame":
                rows = conn.execute(
                    """
                    SELECT skill, ascendancy, tag_signature, builds_count, variant_companion,
                           pob_done, gear_done, gems_done
                    FROM combos
                    WHERE builds_count > 0
                      AND mode = 'league_starter'
                    ORDER BY builds_count DESC
                    """
                ).fetchall()
        else:
            # Pre-migration DB — show all combos regardless of mode
            rows = conn.execute(
                """
                SELECT skill, ascendancy, tag_signature, builds_count, variant_companion,
                       pob_done, gear_done, gems_done
                FROM combos
                WHERE builds_count > 0
                ORDER BY builds_count DESC
                """
            ).fetchall()
    finally:
        conn.close()

    # Load unique-driven mappings once for this request — used by archetype routing
    unique_driven_mappings = _load_unique_driven_builds()

    # Group into archetype buckets
    # Structure: { arch_id: { sub_id | "__all__": [ {skill, ascendancy, builds_count, variant_companion} ] } }
    buckets: dict[str, dict] = {}
    for a in config["archetypes"]:
        if a["id"] in visible:
            buckets[a["id"]] = {}

    for row in rows:
        skill = row["skill"]
        tag_sig = row["tag_signature"] or ""
        variant = row["variant_companion"] or ""
        count = row["builds_count"]
        ascendancy = row["ascendancy"]

        arch_id, sub_id = _assign_archetype(skill, tag_sig, variant, gem_tags, config,
                                            ascendancy=ascendancy,
                                            unique_driven=unique_driven_mappings)

        if arch_id not in visible:
            continue

        bucket = buckets[arch_id]
        key = sub_id or "__all__"
        if key not in bucket:
            bucket[key] = []
        bucket[key].append({
            "skill": skill,
            "ascendancy": ascendancy,
            "builds_count": count,
            "variant_companion": variant,
            "tag_signature": tag_sig,
            "scraped": bool(row["pob_done"]),
        })

    # Serialise: attach archetype metadata
    result = []
    for arch in config["archetypes"]:
        arch_id = arch["id"]
        if arch_id not in visible:
            continue

        bucket = buckets.get(arch_id, {})
        subs = []

        # Unique archetype: subs come from BOTH the gear report scan AND any
        # skill-routed combos that _assign_archetype directed here.
        if arch.get("is_unique_build"):
            routed = buckets.get(arch_id, {})
            subs = _build_unique_subs(mode, routed=routed)
            all_arch_builds = [b for s in subs for b in s["builds"]]
            result.append({
                "id": arch_id,
                "label": arch["label"],
                "icon": arch["icon"],
                "subs": subs,
                "total_builds": sum(b["builds_count"] for b in all_arch_builds),
                "combo_count": len(all_arch_builds),
            })
            continue

        if arch.get("sub"):
            for sub in arch["sub"]:
                children = sub.get("sub")  # nested sub-sub level
                if children:
                    # This sub has its own children (e.g. Crossbow → Grenades/Ammo)
                    subsubs = []
                    child_builds_all = []
                    for child in children:
                        builds = bucket.get(child["id"], [])
                        child_builds_all.extend(builds)
                        if builds:
                            subsubs.append({
                                "id": child["id"],
                                "label": child["label"],
                                "builds": builds,
                                "total": sum(b["builds_count"] for b in builds),
                                "subsubs": None,
                            })
                    if child_builds_all:
                        subs.append({
                            "id": sub["id"],
                            "label": sub["label"],
                            "builds": sorted(child_builds_all, key=lambda b: b["builds_count"], reverse=True),
                            "total": sum(b["builds_count"] for b in child_builds_all),
                            "subsubs": subsubs if subsubs else None,
                        })
                else:
                    builds = bucket.get(sub["id"], [])
                    if builds:
                        subs.append({
                            "id": sub["id"],
                            "label": sub["label"],
                            "builds": builds,
                            "total": sum(b["builds_count"] for b in builds),
                            "subsubs": None,
                        })
        else:
            all_builds = []
            for v in bucket.values():
                all_builds.extend(v)
            all_builds.sort(key=lambda b: b["builds_count"], reverse=True)
            subs = [{
                "id": "__all__",
                "label": "All",
                "builds": all_builds,
                "total": sum(b["builds_count"] for b in all_builds),
                "subsubs": None,
            }] if all_builds else []

        all_arch_builds = [b for s in subs for b in s["builds"]]
        result.append({
            "id": arch_id,
            "label": arch["label"],
            "icon": arch["icon"],
            "subs": subs,
            "total_builds": sum(b["builds_count"] for b in all_arch_builds),
            "combo_count": len(all_arch_builds),
        })

    total = sum(a["total_builds"] for a in result)
    return {"archetypes": result, "total": total, "mode": mode}


# ── Build generation ───────────────────────────────────────────────────────

@router.post("/generate", response_model=BuildGuide)
async def generate(request: BuildRequest):
    """Generate a build guide for a given skill and ascendancy."""
    try:
        guide = await generate_build(request)
        return guide
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
