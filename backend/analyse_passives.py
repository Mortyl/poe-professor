"""
PoB Passive Tree Analyser
--------------------------
Reads tagged JSONL files from pob_codes/ and reports the most commonly taken
passive nodes, filtered by experience level.

Usage:
  python analyse_passives.py --ascendancy Deadeye --experience-level league_starter
  python analyse_passives.py --ascendancy Deadeye --experience-level endgame
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
DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")

# league_starter builds use treeVersion 0_3; endgame builds use 0_4.
# Use the matching tree so node IDs resolve to the correct node names.
TREE_PATH_BY_LEVEL = {
    "league_starter": os.path.join(DATA_DIR, "SkillTreeCore_0_3.json"),
    "endgame":        os.path.join(DATA_DIR, "SkillTreeCore.json"),      # 0_4
}

LEAGUE_STARTER_SNAPSHOTS = {"hour-3", "hour-6", "hour-12", "hour-18", "day-1", "day-2", "day-3"}


def snapshot_matches(snapshot: str, experience_level: str) -> bool:
    if experience_level == "league_starter":
        return snapshot in LEAGUE_STARTER_SNAPSHOTS
    else:
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


def has_skill_with_supports(xml_bytes: bytes, skill: str, min_supports: int = 3) -> bool:
    """Return True only if the build has skill linked to at least min_supports support gems."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return False
    skill_lower = skill.lower()
    for skill_group in root.iter("Skill"):
        gems = skill_group.findall("Gem")
        has_main = any(
            g.attrib.get("nameSpec", "").lower() == skill_lower
            and g.attrib.get("enabled", "true") == "true"
            for g in gems
        )
        if not has_main:
            continue
        supports = [
            g for g in gems
            if g.attrib.get("enabled", "true") == "true"
            and g.attrib.get("nameSpec", "").lower() != skill_lower
            and (
                "Support" in g.attrib.get("gemId", "")
                or "Support" in g.attrib.get("skillId", "")
            )
        ]
        if len(supports) >= min_supports:
            return True
    return False


def extract_nodes(xml_bytes: bytes) -> tuple[list[int], str, str] | None:
    """Return (node_ids, class_name, ascendancy_name) or None."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    build = root.find("Build")
    spec  = root.find(".//Spec")
    if build is None or spec is None:
        return None

    nodes_str = spec.attrib.get("nodes", "")
    node_ids  = [int(n) for n in nodes_str.split(",") if n.strip().isdigit()]
    class_name = build.attrib.get("className", "")
    asc_name   = build.attrib.get("ascendClassName", "")

    return node_ids, class_name, asc_name


def load_entries(experience_level: str, skill: str = "") -> list[dict]:
    skill_lower = skill.lower().strip()
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
                    if not snapshot_matches(obj.get("snapshot", "latest"), experience_level):
                        continue
                    if skill_lower and obj.get("skill", "").lower().strip() != skill_lower:
                        continue
                    entries.append(obj)
                except json.JSONDecodeError:
                    continue
    return entries


def main():
    parser = argparse.ArgumentParser(description="Analyse passive trees from PoB codes")
    parser.add_argument("--ascendancy",       default="Deadeye")
    parser.add_argument("--skill",            default="",
                        help="Filter to builds where the primary skill matches (e.g. 'Lightning Arrow'). "
                             "Leave empty to include all skills for this ascendancy.")
    parser.add_argument("--experience-level", default="endgame",
                        choices=["league_starter", "endgame"])
    parser.add_argument("--top-notables",     type=int, default=40)
    args = parser.parse_args()

    exp = args.experience_level
    tree_path = TREE_PATH_BY_LEVEL[exp]
    print(f"Loading tree data from {tree_path}...")
    with open(tree_path, encoding="utf-8") as f:
        tree_nodes = json.load(f)["Nodes"]

    # Build the set of node IDs that are referenced by at least one other node.
    # Connections are stored one-sidedly in the tree JSON (only one end lists the
    # edge), so a node with an empty Connections dict is NOT necessarily an orphan —
    # it may simply be the "target" end of an edge stored on its neighbour.
    # Using a bidirectional reference set avoids silently dropping valid nodes
    # (e.g. Acceleration at 76.8% adoption was being zeroed out by the old check).
    referenced_ids: set[str] = set(tree_nodes.keys())  # every node references itself
    for n in tree_nodes.values():
        for conn_id in n.get("Connections", {}).keys():
            referenced_ids.add(conn_id)

    skill_label = f" / skill={args.skill}" if args.skill else ""
    print(f"Loading [{exp}] builds from JSONL files{skill_label}...")
    entries = load_entries(exp, args.skill)
    print(f"  {len(entries)} entries match the snapshot filter.")

    if not entries:
        print("No entries found. Run the scraper first.")
        sys.exit(1)

    builds_analysed  = 0
    node_counter:    Counter = Counter()
    notable_counter: Counter = Counter()
    asc_counter:     Counter = Counter()

    for entry in entries:
        xml_bytes = decode_pob(entry["code"])
        if not xml_bytes:
            continue
        # If a skill filter is set, require it to be linked with 3+ supports.
        # This removes builds that appear in the search results but don't
        # genuinely use the skill (e.g. grenadier builds in a LA Deadeye search).
        if args.skill and not has_skill_with_supports(xml_bytes, args.skill, min_supports=3):
            continue
        result = extract_nodes(xml_bytes)
        if not result:
            continue
        node_ids, class_name, asc_name = result

        if args.ascendancy and asc_name.lower() != args.ascendancy.lower():
            continue

        builds_analysed += 1
        for nid in node_ids:
            node = tree_nodes.get(str(nid), {})
            # Skip true orphans — nodes that exist in neither direction of any edge.
            # (Nodes with empty Connections are fine if another node references them.)
            if str(nid) not in referenced_ids:
                continue
            if node.get("Ascendancy"):
                name = node.get("Name", "")
                if name:
                    asc_counter[name] += 1
            else:
                node_counter[nid] += 1
                name = node.get("Name", "")
                if node.get("Type") == 1 and name:
                    notable_counter[name] += 1

    if builds_analysed == 0:
        print(f"No builds found for ascendancy '{args.ascendancy}'.")
        sys.exit(1)

    snapshot_label = "days 1-14" if exp == "league_starter" else "week 3+"
    print(f"\nAnalysed {builds_analysed} {args.ascendancy} builds [{snapshot_label}]\n")

    # ── Text report ──────────────────────────────────────────────────────────
    lines = []
    lines.append("=" * 60)
    lines.append(f"  PASSIVE TREE — {args.ascendancy} ({exp})")
    lines.append(f"  Builds analysed: {builds_analysed}  [{snapshot_label}]")
    lines.append("=" * 60)

    lines.append(f"\n--- TOP {args.top_notables} NOTABLE NODES ---")
    for name, count in notable_counter.most_common(args.top_notables):
        pct = count / builds_analysed * 100
        lines.append(f"  {pct:>5.1f}%  {name}")

    lines.append("\n--- ASCENDANCY NODES ---")
    for name, count in asc_counter.most_common(20):
        pct = count / builds_analysed * 100
        lines.append(f"  {pct:>5.1f}%  {name}")

    report = "\n".join(lines)
    print(report)

    os.makedirs(REPORT_DIR, exist_ok=True)
    asc_slug   = args.ascendancy.lower()
    skill_slug = args.skill.lower().replace(" ", "_") if args.skill else ""
    base_slug  = f"{skill_slug}_{exp}_passives" if skill_slug else f"{asc_slug}_{exp}_passives"
    txt_path   = os.path.join(REPORT_DIR, f"{base_slug}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report)

    # ── JSON report ───────────────────────────────────────────────────────────
    top_nodes = [
        {"id": nid, "pct": round(count / builds_analysed * 100, 1), "count": count,
         "name": tree_nodes.get(str(nid), {}).get("Name", "")}
        for nid, count in node_counter.most_common(300)
    ]
    top_notables = [
        {"name": name, "pct": round(count / builds_analysed * 100, 1), "count": count}
        for name, count in notable_counter.most_common(args.top_notables)
    ]
    top_asc = [
        {"name": name, "pct": round(count / builds_analysed * 100, 1), "count": count}
        for name, count in asc_counter.most_common(20)
    ]
    json_data = {
        "ascendancy":       args.ascendancy,
        "skill":            args.skill,
        "experience_level": exp,
        "builds_analysed":  builds_analysed,
        "snapshot_group":   snapshot_label,
        "top_nodes":        top_nodes,
        "top_notables":     top_notables,
        "top_asc_nodes":    top_asc,
    }
    json_path = os.path.join(REPORT_DIR, f"{base_slug}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)

    print(f"\nText report : {txt_path}")
    print(f"JSON report : {json_path}")


if __name__ == "__main__":
    main()
