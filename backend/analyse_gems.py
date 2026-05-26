"""
PoB Gem Link Analyser
----------------------
Reads PoB codes from JSONL files and extracts per-skill gem linkages.
For each active skill slot in each build, records which support gems
are linked to it, giving accurate per-skill support data.

Usage:
  python analyse_gems.py --skill "Lightning Arrow" --ascendancy Deadeye --experience-level league_starter
"""

import base64
import zlib
import os
import sys
import json
import argparse
import xml.etree.ElementTree as ET
from collections import Counter

# Force UTF-8 stdout so the unicode arrows / em-dashes in our verbose prints
# don't crash on Windows (cp1252 default).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POB_DIR    = os.path.join(os.path.dirname(__file__), "pob_codes")
REPORT_DIR = os.path.join(POB_DIR, "reports")

LEAGUE_STARTER_SNAPSHOTS = {"day-1", "day-2", "day-3", "day-4", "day-5", "latest"}
# Exotic mode pools the wide day-4..week-4 window for low-builds combos
EXOTIC_SNAPSHOTS = {"day-4", "day-5", "day-6", "week-1", "week-2", "week-3", "week-4"}


def snapshot_matches(snapshot: str, experience_level: str) -> bool:
    if experience_level == "league_starter":
        return snapshot in LEAGUE_STARTER_SNAPSHOTS
    if experience_level == "exotic":
        return snapshot in EXOTIC_SNAPSHOTS
    # endgame — anything not league_starter (week-2..week-6 typically)
    return snapshot not in LEAGUE_STARTER_SNAPSHOTS


# ── Tier labels (mirrors analyse_gear.py thresholds) ───────────────────────
def _tier_label(pct: float) -> str:
    if pct >= 85: return "mandatory"
    if pct >= 50: return "recommended"
    if pct >= 25: return "common"
    return "niche"


# ── Skill role classification ──────────────────────────────────────────────
# Curated PoE2 skill-name lists. Names matched case-insensitively. Not
# exhaustive — anything unrecognised is tagged 'secondary' (could be an alt
# damage skill, a triggering skill, or a utility we haven't catalogued).
#
# When a new skill is missing, just append it here. The classifier is
# tolerant: unknown skills aren't broken, they just get the catch-all role.

# "Trigger" skills are themselves "active skills" in PoB2 — when you link
# another active skill as a support beneath them, they fire that skill on
# the trigger condition.
TRIGGER_SUPPORTS: set[str] = {
    "cast on critical", "cast on hit", "cast on block",
    "cast on freeze", "cast on ignite", "cast on shock",
    "cast on stun", "cast on bleed", "cast on minion death",
    "cast on x-rounds",
}

# Spirit-reserved persistent buffs / auras. Adding a new herald or aura
# released in a future patch just means dropping it in here.
AURAS: set[str] = {
    # Heralds
    "herald of ash", "herald of ice", "herald of thunder",
    "herald of plague", "herald of blood",
    # Classic reservation auras
    "hatred", "grace", "determination", "wrath", "anger",
    "vitality", "discipline", "clarity", "haste", "purity of fire",
    "purity of cold", "purity of lightning", "purity of elements",
    # PoE2-specific class auras
    "sigil of power", "sigil of storm",
    "life remnants", "cannibalism",
    "blood and sand", "war banner", "dread banner",
    "blasphemy", "skitterbots",
}

# Standalone curses, walls, mobility, and other non-damage utility skills.
UTILITY_SKILLS: set[str] = {
    # Walls
    "flame wall", "frost wall", "lightning wall",
    # Mobility
    "blink", "flame dash", "shield charge", "leap slam",
    "smoke cloud", "smoke mine",
    # Curses
    "vulnerability", "frostbite", "elemental weakness",
    "conductivity", "flammability", "despair", "enfeeble",
    "temporal chains", "profane ritual",
    # Defensive / utility offensive
    "frost bomb", "bone cage", "plague bearer",
    "molten shell", "vaal molten shell", "bone offering", "flesh offering",
    # Totems / decoys
    "ancestral protector", "decoy totem", "shockwave totem",
}


def _classify_role(name: str, main_skill: str) -> str:
    """Tag a skill_gem with main/trigger/aura/utility/secondary."""
    n = name.lower().strip()
    if n == main_skill.lower().strip():
        return "main"
    if n in TRIGGER_SUPPORTS:
        return "trigger"
    if n in AURAS:
        return "aura"
    if n in UTILITY_SKILLS:
        return "utility"
    return "secondary"


def _detect_trigger_chain(skill_gems: list[dict], main_skill: str) -> list[dict]:
    """
    If a trigger skill_gem (e.g. Cast on Critical) lists the main skill in its
    own supports, return the chain(s) that fire it. Each chain is:
        {trigger_skill: "Cast on Critical", trigger_pct: 99.6}

    Lets the frontend say "Comet is triggered by Cast on Critical" instead of
    leaving the user to guess why both are in the gem list.
    """
    chains: list[dict] = []
    main_lower = main_skill.lower().strip()
    for sg in skill_gems:
        if sg.get("role") != "trigger":
            continue
        for sup in sg.get("supports", []):
            if sup.get("name", "").lower().strip() == main_lower:
                chains.append({
                    "trigger_skill": sg["name"],
                    "trigger_pct":   sg["pct"],
                })
                break
    return chains


def decode_pob(code: str) -> bytes | None:
    code = code.strip().replace("-", "+").replace("_", "/")
    pad  = 4 - len(code) % 4
    if pad != 4:
        code += "=" * pad
    try:
        return zlib.decompress(base64.b64decode(code))
    except Exception:
        return None


def has_main_skill(xml_bytes: bytes, skill: str, min_supports: int = 2) -> bool:
    """Return True if this build has the main skill linked to at least min_supports gems."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return False
    skill_lower = skill.lower()
    for skill_elem in root.iter("Skill"):
        gems = skill_elem.findall("Gem")
        enabled_gems = [g for g in gems if g.attrib.get("enabled", "true") == "true"]
        names = [g.attrib.get("nameSpec", "").strip() for g in enabled_gems]
        if skill_lower in [n.lower() for n in names]:
            non_main = [n for n in names if n.lower() != skill_lower and n]
            if len(non_main) >= min_supports:
                return True
    return False


def extract_skill_groups(xml_bytes: bytes) -> list[dict] | None:
    """
    Parse PoB XML and return all skill groups as:
    [{"active": "Skill Name", "supports": ["Support1", "Support2", ...]}, ...]

    In PoB2, the first enabled gem in a Skill group is the active skill;
    all subsequent enabled gems are support gems.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    groups = []
    for skill_elem in root.iter("Skill"):
        if skill_elem.attrib.get("enabled", "true") == "false":
            continue
        enabled_gems = [
            g for g in skill_elem.findall("Gem")
            if g.attrib.get("enabled", "true") == "true"
            and g.attrib.get("nameSpec", "").strip()
        ]
        if not enabled_gems:
            continue

        active  = enabled_gems[0].attrib.get("nameSpec", "").strip()
        supports = [g.attrib.get("nameSpec", "").strip() for g in enabled_gems[1:] if g.attrib.get("nameSpec", "").strip()]

        if active:
            groups.append({"active": active, "supports": supports})

    return groups if groups else None


def load_entries(experience_level: str, skill: str, ascendancy: str,
                 variant_skill: str = '', item: str = '') -> list[dict]:
    from util import slug_for_skill
    if item:
        slug = f"{slug_for_skill(item)}_"
    elif variant_skill:
        slug = f"{slug_for_skill(skill)}_{slug_for_skill(variant_skill)}_{ascendancy.lower()}_"
    else:
        slug = f"{slug_for_skill(skill)}_{ascendancy.lower()}_"
    entries = []
    for fname in sorted(os.listdir(POB_DIR)):
        if not fname.endswith(".jsonl"):
            continue
        if slug not in fname.lower():
            continue
        with open(os.path.join(POB_DIR, fname), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if item:
                        # Item-scraped files already contain only the right snapshots
                        entries.append(obj)
                    elif not snapshot_matches(obj.get("snapshot", "latest"), experience_level):
                        continue
                    else:
                        entries.append(obj)
                except json.JSONDecodeError:
                    continue
    return entries


def analyse(skill: str, ascendancy: str, experience_level: str,
            variant_skill: str = '', item: str = '',
            max_skills: int = 9, max_supports: int = 6,
            verbose: bool = True) -> dict | None:
    """
    Run the gem-link analysis and write the report.
    Returns the report dict, or None if no valid builds were found.
    """
    exp = experience_level
    snapshot_label = (
        "days 1-14" if exp == "league_starter"
        else "day-4 → week-4 (exotic pool)" if exp == "exotic"
        else "week 3+"
    )

    label = item if item else f"{skill}{' + ' + variant_skill if variant_skill else ''} / {ascendancy}"
    if verbose:
        print(f"Loading [{exp}] builds for {label}...")
    entries = load_entries(exp, skill, ascendancy, variant_skill, item)
    if verbose:
        print(f"  {len(entries)} raw entries found in JSONL files")

    if not entries:
        if verbose:
            print("No entries found. Run scrape_poeninja.py first.")
        return None

    builds_analysed = 0
    support_counts: dict[str, Counter] = {}
    skill_build_counts: Counter = Counter()

    main_skill = item if item else skill

    for entry in entries:
        xml_bytes = decode_pob(entry.get("code", ""))
        if not xml_bytes:
            continue
        # Item-mode skips the main-skill filter (item builds don't share a single skill)
        if not item and not has_main_skill(xml_bytes, skill, min_supports=2):
            continue

        groups = extract_skill_groups(xml_bytes)
        if not groups:
            continue

        builds_analysed += 1
        for group in groups:
            active = group["active"]
            skill_build_counts[active] += 1
            if active not in support_counts:
                support_counts[active] = Counter()
            for sup in group["supports"]:
                support_counts[active][sup] += 1

    if builds_analysed == 0:
        if verbose:
            print(f"No valid builds found for {label}.")
        return None

    if verbose:
        print(f"\nAnalysed {builds_analysed} builds\n")

    top_skills = skill_build_counts.most_common(max_skills)

    skill_gems_out = []
    for skill_name, skill_count in top_skills:
        skill_pct = round(skill_count / builds_analysed * 100, 1)
        top_sups  = support_counts.get(skill_name, Counter()).most_common(max_supports)
        sup_out   = [
            {
                "name": sup,
                "pct":  round(count / skill_count * 100, 1),
                "tier": _tier_label(round(count / skill_count * 100, 1)),
            }
            for sup, count in top_sups
        ]
        skill_gems_out.append({
            "name":     skill_name,
            "pct":      skill_pct,
            "tier":     _tier_label(skill_pct),
            "role":     _classify_role(skill_name, main_skill),
            "supports": sup_out,
        })

    # ── Trigger chain detection ──────────────────────────────────────────
    # For each trigger-role skill_gem that lists the main skill among its
    # supports, emit "main skill is triggered by this." Lets the UI show
    # "Comet is triggered by Cast on Critical" without the user inferring it.
    trigger_chains = _detect_trigger_chain(skill_gems_out, main_skill)
    if trigger_chains:
        for sg in skill_gems_out:
            if sg.get("role") == "main":
                sg["triggered_by"] = trigger_chains
                break

    if verbose:
        print(f"--- SKILL GEMS ---")
        for sg in skill_gems_out:
            tag = sg["role"]
            chain = ""
            if sg.get("triggered_by"):
                chain = "  ← triggered by " + ", ".join(c["trigger_skill"] for c in sg["triggered_by"])
            print(f"  {sg['pct']:>5.1f}%  [{tag:9s}] {sg['name']}{chain}")
            for s in sg["supports"]:
                print(f"           {s['pct']:>5.1f}%  [{s['tier']:11s}] {s['name']}")

    # ── Write report ─────────────────────────────────────────────────────
    os.makedirs(REPORT_DIR, exist_ok=True)
    from util import slug_for_skill
    asc_slug = ascendancy.lower()
    if item:
        gems_path = os.path.join(REPORT_DIR, f"{slug_for_skill(item)}_{exp}_gems.json")
    elif variant_skill:
        gems_path = os.path.join(REPORT_DIR, f"{slug_for_skill(skill)}_{slug_for_skill(variant_skill)}_{asc_slug}_{exp}_gems.json")
    else:
        gems_path = os.path.join(REPORT_DIR, f"{slug_for_skill(skill)}_{asc_slug}_{exp}_gems.json")

    gems_data = {
        "ascendancy":       "Any" if item else ascendancy,
        "skill":            main_skill,
        "experience_level": exp,
        "builds_analysed":  builds_analysed,
        "snapshot_group":   snapshot_label,
        "source":           "poe.ninja PoB codes",
        "skill_gems":       skill_gems_out,
        "trigger_chains":   trigger_chains,
    }
    if item:
        gems_data["item"] = item
    with open(gems_path, "w", encoding="utf-8") as f:
        json.dump(gems_data, f, indent=2)

    if verbose:
        print(f"\nGems report : {gems_path}")

    return gems_data


def main():
    parser = argparse.ArgumentParser(description="Analyse gem links from PoB codes")
    parser.add_argument("--skill",            default="Lightning Arrow", help="Primary skill, e.g. 'Lightning Arrow'")
    parser.add_argument("--ascendancy",       default="Deadeye",         help="Ascendancy, e.g. 'Deadeye'")
    parser.add_argument("--item",             default="",
                        help="Unique item name — analyse builds scraped with --item. "
                             "Overrides --skill/--ascendancy.")
    parser.add_argument("--experience-level", default="league_starter",
                        choices=["league_starter", "endgame", "exotic"])
    parser.add_argument("--max-skills",       type=int, default=9,
                        help="Max active skills to include in report (default 9)")
    parser.add_argument("--max-supports",     type=int, default=6,
                        help="Max supports per skill to include in report (default 6)")
    parser.add_argument("--variant-skill",    default="",
                        help="If set, read JSONL files for this variant and include variant slug in output filename.")
    args = parser.parse_args()

    result = analyse(
        skill=args.skill, ascendancy=args.ascendancy,
        experience_level=args.experience_level,
        variant_skill=args.variant_skill, item=args.item,
        max_skills=args.max_skills, max_supports=args.max_supports,
        verbose=True,
    )
    if result is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
