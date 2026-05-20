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
    if item:
        item_slug = item.lower().replace(" ", "_").replace("'", "").replace(",", "")
        slug = f"{item_slug}_"
    elif variant_skill:
        variant_slug_part = variant_skill.lower().replace(' ', '_')
        slug = f"{skill.lower().replace(' ', '_')}_{variant_slug_part}_{ascendancy.lower()}_"
    else:
        slug = f"{skill.lower().replace(' ', '_')}_{ascendancy.lower()}_"
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

    exp = args.experience_level
    snapshot_label = (
        "days 1-14" if exp == "league_starter"
        else "day-4 → week-4 (exotic pool)" if exp == "exotic"
        else "week 3+"
    )

    label = args.item if args.item else f"{args.skill}{' + ' + args.variant_skill if args.variant_skill else ''} / {args.ascendancy}"
    print(f"Loading [{exp}] builds for {label}...")
    entries = load_entries(exp, args.skill, args.ascendancy, args.variant_skill, args.item)
    print(f"  {len(entries)} raw entries found in JSONL files")

    if not entries:
        print("No entries found. Run scrape_poeninja.py first.")
        sys.exit(1)

    builds_analysed = 0
    # active_skill -> Counter of support gem names
    support_counts: dict[str, Counter] = {}
    # active_skill -> how many builds use it
    skill_build_counts: Counter = Counter()

    for entry in entries:
        xml_bytes = decode_pob(entry.get("code", ""))
        if not xml_bytes:
            continue
        # Only count builds where the main skill is genuinely linked with 2+ supports
        if not has_main_skill(xml_bytes, args.skill, min_supports=2):
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
        print(f"No valid builds found for {args.skill} / {args.ascendancy}.")
        sys.exit(1)

    print(f"\nAnalysed {builds_analysed} builds\n")

    # Sort active skills by how many builds use them (descending)
    top_skills = skill_build_counts.most_common(args.max_skills)

    print(f"--- SKILL GEMS ---")
    skill_gems_out = []
    for skill_name, skill_count in top_skills:
        skill_pct = skill_count / builds_analysed * 100
        top_sups  = support_counts.get(skill_name, Counter()).most_common(args.max_supports)
        sup_out   = [
            {"name": sup, "pct": round(count / skill_count * 100, 1)}
            for sup, count in top_sups
        ]
        print(f"  {skill_pct:>5.1f}%  {skill_name}")
        for s in sup_out:
            print(f"           {s['pct']:>5.1f}%  {s['name']}")
        skill_gems_out.append({
            "name":     skill_name,
            "pct":      round(skill_pct, 1),
            "supports": sup_out,
        })

    # ── Write report ─────────────────────────────────────────────────────────
    os.makedirs(REPORT_DIR, exist_ok=True)
    # Filename includes the ascendancy (and variant) so different ascendancies playing
    # the same skill don't overwrite each other's report.
    asc_slug = args.ascendancy.lower()
    if args.item:
        item_slug = args.item.lower().replace(" ", "_").replace("'", "").replace(",", "")
        gems_path = os.path.join(REPORT_DIR, f"{item_slug}_{exp}_gems.json")
    elif args.variant_skill:
        skill_slug        = args.skill.lower().replace(" ", "_")
        variant_slug_part = args.variant_skill.lower().replace(" ", "_")
        gems_path = os.path.join(REPORT_DIR, f"{skill_slug}_{variant_slug_part}_{asc_slug}_{exp}_gems.json")
    else:
        skill_slug = args.skill.lower().replace(" ", "_")
        gems_path = os.path.join(REPORT_DIR, f"{skill_slug}_{asc_slug}_{exp}_gems.json")

    gems_data = {
        "ascendancy":       "Any" if args.item else args.ascendancy,
        "skill":            args.item if args.item else args.skill,
        "experience_level": exp,
        "builds_analysed":  builds_analysed,
        "snapshot_group":   snapshot_label,
        "source":           "poe.ninja PoB codes",
        "skill_gems":       skill_gems_out,
    }
    if args.item:
        gems_data["item"] = args.item
    with open(gems_path, "w", encoding="utf-8") as f:
        json.dump(gems_data, f, indent=2)

    print(f"\nGems report : {gems_path}")


if __name__ == "__main__":
    main()
