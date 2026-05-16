"""
PoB Build Batch Analyser
------------------------
Decodes all PoB export codes in pob_codes/ and produces a consensus report.

Each .txt file can contain either:
  - A single PoB export code
  - Multiple codes, one per line

Usage:
  python analyse_builds.py [--filter-class Ranger] [--filter-asc Deadeye]
"""

import base64
import zlib
import json
import os
import sys
import argparse
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

POB_DIR    = os.path.join(os.path.dirname(__file__), "pob_codes")
TREE_PATH  = os.path.join(os.path.dirname(__file__), "data", "SkillTreeCore.json")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "pob_codes", "reports")


def decode_pob(code: str) -> bytes | None:
    code = code.strip().replace("-", "+").replace("_", "/")
    pad  = 4 - len(code) % 4
    if pad != 4:
        code += "=" * pad
    try:
        return zlib.decompress(base64.b64decode(code))
    except Exception:
        return None


def parse_build(xml_bytes: bytes) -> dict | None:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    build = root.find("Build")
    if build is None:
        return None

    spec = root.find(".//Spec")
    if spec is None:
        return None

    nodes_str = spec.attrib.get("nodes", "")
    node_ids  = [int(n) for n in nodes_str.split(",") if n.strip().isdigit()]

    return {
        "class":      build.attrib.get("className", ""),
        "ascendancy": build.attrib.get("ascendClassName", ""),
        "level":      int(build.attrib.get("level", 0)),
        "nodes":      node_ids,
    }


def load_codes_from_dir(directory: str) -> list[str]:
    codes = []
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".txt"):
            continue
        if fname.startswith("_"):       # skip report files
            continue
        fpath = os.path.join(directory, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if len(line) > 100:     # PoB codes are always very long
                    codes.append(line)
    return codes


def analyse(builds: list[dict], tree_nodes: dict) -> dict:
    total = len(builds)

    # Per-node counts
    node_counter: Counter = Counter()
    # Per-stat counts and total values
    stat_presence: Counter = Counter()   # how many builds have this stat
    stat_total:    Counter = Counter()   # sum of values across builds

    # Notable names
    notable_counter: Counter = Counter()

    for b in builds:
        seen_stats = set()
        for nid in b["nodes"]:
            n = tree_nodes.get(str(nid), {})
            if n.get("Ascendancy"):
                continue            # analyse ascendancy separately

            node_counter[nid] += 1
            name = n.get("Name", "")
            if n.get("Type") == 1 and name:
                notable_counter[name] += 1

            for stat_key, val in (n.get("Stats") or {}).items():
                stat_total[stat_key] += val
                if stat_key not in seen_stats:
                    stat_presence[stat_key] += 1
                    seen_stats.add(stat_key)

    # Ascendancy nodes separately
    asc_node_counter: Counter = Counter()
    for b in builds:
        for nid in b["nodes"]:
            n = tree_nodes.get(str(nid), {})
            if n.get("Ascendancy"):
                name = n.get("Name", "")
                if name:
                    asc_node_counter[name] += 1

    return {
        "total":           total,
        "stat_presence":   stat_presence,
        "stat_total":      stat_total,
        "node_counter":    node_counter,
        "notable_counter": notable_counter,
        "asc_counter":     asc_node_counter,
    }


def print_report(result: dict, tree_nodes: dict, filter_class: str, filter_asc: str):
    total = result["total"]
    stat_presence   = result["stat_presence"]
    stat_total      = result["stat_total"]
    notable_counter = result["notable_counter"]
    asc_counter     = result["asc_counter"]

    label = f"{filter_class} {filter_asc}".strip() or "All Builds"
    lines = []
    lines.append("=" * 70)
    lines.append(f"  BUILD ANALYSIS — {label}")
    lines.append(f"  Builds analysed: {total}")
    lines.append("=" * 70)

    lines.append("\n--- STAT CONSENSUS (main tree, sorted by % of builds) ---")
    lines.append(f"{'Stat Key':<60} {'% builds':>8}  {'avg val':>8}")
    lines.append("-" * 80)
    for stat, count in stat_presence.most_common(50):
        pct = count / total * 100
        avg = stat_total[stat] / total
        lines.append(f"{stat:<60} {pct:>7.1f}%  {avg:>8.1f}")

    lines.append("\n--- NOTABLE NODES (sorted by % of builds) ---")
    for name, count in notable_counter.most_common(30):
        pct = count / total * 100
        lines.append(f"  {pct:>5.1f}%  {name}")

    lines.append("\n--- ASCENDANCY NODES (sorted by % of builds) ---")
    for name, count in asc_counter.most_common(20):
        pct = count / total * 100
        lines.append(f"  {pct:>5.1f}%  {name}")

    report = "\n".join(lines)
    print(report)

    # Save to file
    os.makedirs(REPORT_DIR, exist_ok=True)
    fname = f"{'_'.join((label).lower().split())}_report.txt"
    fpath = os.path.join(REPORT_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to: {fpath}")


def main():
    parser = argparse.ArgumentParser(description="Analyse PoB build codes")
    parser.add_argument("--filter-class", default="",  help="e.g. Ranger")
    parser.add_argument("--filter-asc",   default="",  help="e.g. Deadeye")
    args = parser.parse_args()

    print(f"Loading tree data...")
    with open(TREE_PATH, encoding="utf-8") as f:
        tree_nodes = json.load(f)["Nodes"]

    print(f"Reading PoB codes from {POB_DIR}...")
    codes = load_codes_from_dir(POB_DIR)
    print(f"Found {len(codes)} codes to decode.")

    builds = []
    failed = 0
    for i, code in enumerate(codes):
        xml_bytes = decode_pob(code)
        if not xml_bytes:
            failed += 1
            continue
        build = parse_build(xml_bytes)
        if not build:
            failed += 1
            continue

        # Apply filters
        if args.filter_class and build["class"].lower() != args.filter_class.lower():
            continue
        if args.filter_asc and build["ascendancy"].lower() != args.filter_asc.lower():
            continue

        builds.append(build)

    print(f"Decoded: {len(builds)} valid builds  |  Failed/filtered: {failed + (len(codes) - len(builds) - failed)}")

    if not builds:
        print("No builds matched the filters. Exiting.")
        sys.exit(1)

    result = analyse(builds, tree_nodes)
    print_report(result, tree_nodes, args.filter_class, args.filter_asc)


if __name__ == "__main__":
    main()
