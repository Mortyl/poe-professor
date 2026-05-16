"""
PoB Gem Link Analyser
---------------------
Reads tagged JSONL files from pob_codes/ and reports the most common support
gems linked to a given main skill, filtered by experience level.

Experience level snapshot groups:
  league_starter — hour-12, hour-18, day-1, day-2
  endgame        — week-3 onwards + latest

Usage:
  python analyse_gem_links.py --skill "Lightning Arrow" --experience-level league_starter
  python analyse_gem_links.py --skill "Lightning Arrow" --experience-level endgame --top 15
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

LEAGUE_STARTER_SNAPSHOTS = {"hour-12", "hour-18", "day-1", "day-2"}


def snapshot_matches(snapshot: str, experience_level: str) -> bool:
    if experience_level == "league_starter":
        return snapshot in LEAGUE_STARTER_SNAPSHOTS
    else:  # endgame
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


def extract_gem_links(xml_bytes: bytes, main_skill: str) -> list[str] | None:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    main_skill_lower = main_skill.lower()

    for skill_group in root.iter("Skill"):
        gems = skill_group.findall("Gem")

        main_found = any(
            g.attrib.get("nameSpec", "").lower() == main_skill_lower
            and g.attrib.get("enabled", "true") == "true"
            for g in gems
        )
        if not main_found:
            continue

        supports = []
        for g in gems:
            name     = g.attrib.get("nameSpec", "")
            gem_id   = g.attrib.get("gemId", "")
            skill_id = g.attrib.get("skillId", "")
            enabled  = g.attrib.get("enabled", "true") == "true"

            if not enabled or not name or not gem_id:
                continue
            if name.lower() == main_skill_lower:
                continue

            if "Support" in gem_id or "Support" in skill_id:
                # Strip roman numeral tier suffix
                clean = name.rstrip(" I").rstrip(" V").rstrip(" X").strip()
                supports.append(clean)

        return supports

    return None


def load_entries(experience_level: str) -> list[dict]:
    """Load JSONL entries filtered to the right snapshot group."""
    entries = []
    for fname in sorted(os.listdir(POB_DIR)):
        if not fname.endswith(".jsonl"):
            continue
        with open(os.path.join(POB_DIR, fname), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if snapshot_matches(obj.get("snapshot", "latest"), experience_level):
                        entries.append(obj)
                except json.JSONDecodeError:
                    continue
    return entries


def main():
    parser = argparse.ArgumentParser(description="Analyse gem links from PoB codes")
    parser.add_argument("--skill",             default="Lightning Arrow")
    parser.add_argument("--experience-level",  default="endgame",
                        choices=["league_starter", "endgame"])
    parser.add_argument("--top",               type=int, default=12)
    args = parser.parse_args()

    exp = args.experience_level
    print(f"Loading [{exp}] builds from JSONL files...")
    entries = load_entries(exp)
    print(f"  {len(entries)} entries match the snapshot filter.")

    if not entries:
        print("No entries found. Run the scraper first with --snapshots.")
        sys.exit(1)

    support_counter: Counter = Counter()
    builds_with_skill = 0
    full_links: list[frozenset] = []

    for entry in entries:
        xml_bytes = decode_pob(entry["code"])
        if not xml_bytes:
            continue
        supports = extract_gem_links(xml_bytes, args.skill)
        if supports is None:
            continue
        builds_with_skill += 1
        for s in supports:
            support_counter[s] += 1
        full_links.append(frozenset(supports))

    if builds_with_skill == 0:
        print(f"No builds found with skill '{args.skill}'.")
        sys.exit(1)

    print(f"Found '{args.skill}' in {builds_with_skill} builds.\n")

    snapshot_label = "days 1-14" if exp == "league_starter" else "week 3+"

    # ── Text report ──────────────────────────────────────────────────────────
    lines = []
    lines.append("=" * 60)
    lines.append(f"  GEM LINKS — {args.skill} ({exp})")
    lines.append(f"  Builds analysed: {builds_with_skill}  [{snapshot_label}]")
    lines.append("=" * 60)
    lines.append(f"\n--- TOP {args.top} SUPPORT GEMS ---")
    lines.append(f"{'Support Gem':<40} {'% builds':>8}  {'count':>6}")
    lines.append("-" * 58)
    for gem, count in support_counter.most_common(args.top):
        pct = count / builds_with_skill * 100
        lines.append(f"{gem:<40} {pct:>7.1f}%  {count:>6}")

    link_counter: Counter = Counter(full_links)
    lines.append("\n--- MOST COMMON FULL LINK SETS ---")
    for link_set, count in link_counter.most_common(5):
        pct = count / builds_with_skill * 100
        gems = " + ".join(sorted(link_set)) if link_set else "(no supports)"
        lines.append(f"  {pct:>5.1f}%  [{gems}]")

    report = "\n".join(lines)
    print(report)

    os.makedirs(REPORT_DIR, exist_ok=True)
    slug = args.skill.lower().replace(" ", "_")
    txt_path = os.path.join(REPORT_DIR, f"{slug}_{exp}_gem_links.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report)

    # ── JSON report (machine-readable for build service) ─────────────────────
    top_supports = [
        {"name": gem, "pct": round(count / builds_with_skill * 100, 1), "count": count}
        for gem, count in support_counter.most_common(args.top)
    ]
    top_link_sets = [
        {"gems": sorted(link_set), "pct": round(count / builds_with_skill * 100, 1), "count": count}
        for link_set, count in link_counter.most_common(3)
    ]
    json_data = {
        "skill":            args.skill,
        "experience_level": exp,
        "builds_analysed":  builds_with_skill,
        "snapshot_group":   snapshot_label,
        "top_supports":     top_supports,
        "top_link_sets":    top_link_sets,
    }
    json_path = os.path.join(REPORT_DIR, f"{slug}_{exp}_gem_links.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)

    print(f"\nText report : {txt_path}")
    print(f"JSON report : {json_path}")


if __name__ == "__main__":
    main()
