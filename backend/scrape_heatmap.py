"""
PoE Ninja Heatmap Scraper
--------------------------
Fetches passive node allocation data from poe.ninja's builds search API
and converts it to the standard JSON report format used by tree_service.py.

HOW IT WORKS:
  poe.ninja's builds search API returns a protobuf response containing:
    1. A "passiveids" dimension with (sequential_id, count) pairs
    2. Dictionary references, each with a hash

  Fetching /poe2/api/builds/dictionary/{hash} for the "passiveid" dictionary
  returns an array: values[sequential_id] = GGG_node_id_string

  This gives us the true poe.ninja → GGG node ID mapping.

Usage:
  python scrape_heatmap.py --skill "Lightning Arrow" --ascendancy Deadeye --snapshots week-3
  python scrape_heatmap.py --skill "Poisonburst Arrow" --ascendancy Pathfinder --snapshots day-1,day-2,day-3,day-4
  python scrape_heatmap.py --help
"""

import sys
import json
import os
import argparse
import urllib.request
import urllib.parse
import time
import random

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPORT_DIR = os.path.join(os.path.dirname(__file__), "pob_codes", "reports")
DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
TREE_PATH  = os.path.join(DATA_DIR, "SkillTreeCore.json")

DICT_CACHE: dict[str, list[str]] = {}  # hash -> values list (GGG ID strings)

LEAGUE_STARTER_SNAPSHOTS = {"day-1", "day-2", "day-3", "day-4"}


# ── Protobuf helpers ─────────────────────────────────────────────────────────

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
    """Parse protobuf into {field_num: [values]} where values are bytes/int."""
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


# ── Network helpers ──────────────────────────────────────────────────────────

def fetch(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_snapshot(league: str = "sc") -> tuple[str, str, list[str]]:
    raw = fetch("https://poe.ninja/poe2/api/data/index-state")
    data = json.loads(raw)
    for snap in data.get("snapshotVersions", []):
        url   = snap.get("url", "")
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
            labels = snap.get("timeMachineLabels", [])
            return snap["version"], snap["snapshotName"], labels
    raise RuntimeError(f"Could not find snapshot for league '{league}'")


# ── Fetch one snapshot's heatmap data ────────────────────────────────────────

def fetch_heatmap_snapshot(
    snapshot: str, snapshot_name: str,
    ascendancy: str, skill: str, time_machine: str
) -> tuple[dict[int, int], int] | None:
    """
    Returns (ggg_node_id -> count, total_builds) for one snapshot,
    or None on failure.
    """
    skill_enc = urllib.parse.quote(skill.replace(" ", "+"), safe="+")
    asc_enc   = urllib.parse.quote(ascendancy, safe="")
    url = (
        f"https://poe.ninja/poe2/api/builds/{snapshot}/search"
        f"?class={asc_enc}"
        f"&skills={skill_enc}"
        f"&timemachine={urllib.parse.quote(time_machine)}"
        f"&heatmap=true"
        f"&overview={snapshot_name}"
    )
    print(f"  GET {url}")
    try:
        raw = fetch(url)
    except Exception as e:
        print(f"  ERROR fetching search: {e}")
        return None

    # Parse NinjaSearchResult proto
    # Outer: field 1 (bytes) = SearchResult
    outer_f = parse_fields(raw)
    if 1 not in outer_f or not isinstance(outer_f[1][0], bytes):
        print("  ERROR: unexpected outer proto structure")
        return None
    inner_bytes = outer_f[1][0]

    # Parse SearchResult
    # field 1 (varint) = total
    # field 2 (repeated bytes) = dimensions (SearchResultDimension)
    # field 6 (repeated bytes) = dictionaries (SearchResultDictionaryReference)
    inner_f = parse_fields(inner_bytes)

    total = inner_f.get(1, [0])[0]
    if not isinstance(total, int):
        total = 0
    print(f"  Total builds: {total}")

    # Parse dictionary references: {field1=id, field2=hash}
    dict_refs: dict[str, str] = {}  # id -> hash
    for ref_bytes in inner_f.get(6, []):
        if not isinstance(ref_bytes, bytes):
            continue
        rf = parse_fields(ref_bytes)
        ref_id   = rf.get(1, [b""])[0].decode("utf-8") if isinstance(rf.get(1, [None])[0], bytes) else ""
        ref_hash = rf.get(2, [b""])[0].decode("utf-8") if isinstance(rf.get(2, [None])[0], bytes) else ""
        if ref_id and ref_hash:
            dict_refs[ref_id] = ref_hash
    print(f"  Dictionaries found: {sorted(dict_refs.keys())}")

    if "passiveid" not in dict_refs:
        print("  ERROR: no passiveid dictionary reference in response")
        return None

    # Fetch passiveid dictionary (cached)
    dict_hash = dict_refs["passiveid"]
    if dict_hash not in DICT_CACHE:
        dict_url = f"https://poe.ninja/poe2/api/builds/dictionary/{dict_hash}"
        print(f"  Fetching dictionary: {dict_url}")
        try:
            dict_raw = fetch(dict_url)
        except Exception as e:
            print(f"  ERROR fetching dictionary: {e}")
            return None
        df = parse_fields(dict_raw)
        # field 2 = repeated string values (GGG node ID strings)
        values = [
            v.decode("utf-8") if isinstance(v, bytes) else ""
            for v in df.get(2, [])
        ]
        DICT_CACHE[dict_hash] = values
        print(f"  Dictionary loaded: {len(values)} entries")
    else:
        values = DICT_CACHE[dict_hash]
        print(f"  Dictionary from cache: {len(values)} entries")

    # Fetch gem dictionary (for allskills dimension)
    gem_values: list[str] = []
    if "gem" in dict_refs:
        gem_hash = dict_refs["gem"]
        if gem_hash not in DICT_CACHE:
            gem_url = f"https://poe.ninja/poe2/api/builds/dictionary/{gem_hash}"
            print(f"  Fetching gem dictionary: {gem_url}")
            try:
                gem_raw = fetch(gem_url)
                gf = parse_fields(gem_raw)
                gem_values = [
                    v.decode("utf-8") if isinstance(v, bytes) else ""
                    for v in gf.get(2, [])
                ]
                DICT_CACHE[gem_hash] = gem_values
                print(f"  Gem dictionary loaded: {len(gem_values)} entries")
            except Exception as e:
                print(f"  WARNING: could not fetch gem dictionary: {e}")
        else:
            gem_values = DICT_CACHE[gem_hash]

    # Parse passiveids, skills (active only), and allskills (active + supports)
    ggg_counts:    dict[int, int] = {}
    active_counts: dict[str, int] = {}  # skills dimension — active skills only
    all_counts:    dict[str, int] = {}  # allskills dimension — active + supports

    for dim_bytes in inner_f.get(2, []):
        if not isinstance(dim_bytes, bytes):
            continue
        df2 = parse_fields(dim_bytes)
        dim_id = df2.get(1, [b""])[0].decode("utf-8") if isinstance(df2.get(1, [None])[0], bytes) else ""

        if dim_id == "passiveids":
            for cnt_bytes in df2.get(3, []):
                if not isinstance(cnt_bytes, bytes):
                    continue
                cf = parse_fields(cnt_bytes)
                seq_id = cf.get(1, [0])[0]
                count  = cf.get(2, [0])[0]
                if not isinstance(seq_id, int) or not isinstance(count, int):
                    continue
                if seq_id < len(values) and values[seq_id]:
                    try:
                        ggg_id = int(values[seq_id])
                        ggg_counts[ggg_id] = count
                    except ValueError:
                        pass

        elif dim_id in ("skills", "allskills") and gem_values:
            target = active_counts if dim_id == "skills" else all_counts
            for cnt_bytes in df2.get(3, []):
                if not isinstance(cnt_bytes, bytes):
                    continue
                cf = parse_fields(cnt_bytes)
                seq_id = cf.get(1, [0])[0]
                count  = cf.get(2, [0])[0]
                if not isinstance(seq_id, int) or not isinstance(count, int):
                    continue
                if seq_id < len(gem_values) and gem_values[seq_id]:
                    target[gem_values[seq_id]] = count

    # Anything in active_counts is a confirmed active skill.
    # Anything in all_counts but NOT in active_counts is a support gem.
    support_counts: dict[str, int] = {
        name: count for name, count in all_counts.items()
        if name not in active_counts
    }

    print(f"  Mapped {len(ggg_counts)} passive nodes, "
          f"{len(active_counts)} active skills, {len(support_counts)} supports")
    return ggg_counts, active_counts, support_counts, total


# ── Aggregate across snapshots ────────────────────────────────────────────────

def aggregate_snapshots(
    snapshot: str, snapshot_name: str,
    ascendancy: str, skill: str, labels: list[str]
) -> tuple[dict[int, float], dict[str, float], dict[str, float], int]:
    """
    Fetch and aggregate heatmap data across multiple snapshots.
    Returns (ggg_node_id -> avg_pct, active_skill -> avg_pct, support -> avg_pct, total_builds).
    """
    accum:          dict[int, list[int]] = {}
    active_accum:   dict[str, list[int]] = {}
    support_accum:  dict[str, list[int]] = {}
    builds_per:     list[int] = []

    for label in labels:
        print(f"\n--- Snapshot: {label or 'latest'} ---")
        result = fetch_heatmap_snapshot(snapshot, snapshot_name, ascendancy, skill, label)
        if result is None:
            continue
        ggg_counts, active_counts, support_counts, total = result
        builds_per.append(total)
        for ggg_id, count in ggg_counts.items():
            accum.setdefault(ggg_id, []).append(count)
        for name, count in active_counts.items():
            active_accum.setdefault(name, []).append(count)
        for name, count in support_counts.items():
            support_accum.setdefault(name, []).append(count)
        time.sleep(random.uniform(1.5, 4.0))

    if not builds_per:
        return {}, {}, {}, 0

    total_builds = max(builds_per)

    def avg_pct(accum_dict: dict) -> dict:
        return {
            name: (sum(counts) / len(counts)) / total_builds * 100
            for name, counts in accum_dict.items()
        }

    return avg_pct(accum), avg_pct(active_accum), avg_pct(support_accum), total_builds


# ── Load tree metadata ────────────────────────────────────────────────────────

def load_tree_nodes() -> dict[int, dict]:
    with open(TREE_PATH, encoding="utf-8") as f:
        tree = json.load(f)
    return {int(k): v for k, v in tree.get("Nodes", {}).items()}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape passive heatmap from poe.ninja builds API")
    parser.add_argument("--skill",       required=True, help="Skill name, e.g. 'Lightning Arrow'")
    parser.add_argument("--ascendancy",  required=True, help="Ascendancy name, e.g. 'Deadeye'")
    parser.add_argument("--league",      default="sc",
                        choices=["sc", "hc", "ssf", "hcssf"])
    parser.add_argument("--snapshots",   default="day-1,day-2,day-3,day-4",
                        help="Comma-separated time-machine labels, e.g. 'day-1,day-2,day-3,day-4'.")
    parser.add_argument("--experience-level", default="league_starter",
                        choices=["league_starter", "endgame", "exotic"])
    parser.add_argument("--top-notables", type=int, default=50)
    parser.add_argument("--skip-gems",     action="store_true",
                        help="Skip gem report generation (write passives only). "
                             "Use with day-1,2,3,4 snapshots for the passives pipeline.")
    parser.add_argument("--skip-passives", action="store_true",
                        help="Skip passive report generation (write gems only). "
                             "Use with day-2,3,4 snapshots for the gems pipeline.")
    args = parser.parse_args()

    os.makedirs(REPORT_DIR, exist_ok=True)

    print(f"Getting snapshot for [{args.league.upper()}]...")
    snapshot, snapshot_name, available_labels = get_snapshot(args.league)
    print(f"  Snapshot : {snapshot} ({snapshot_name})")
    print(f"  Available: {sorted(available_labels)}")

    requested = [l.strip() for l in args.snapshots.split(",") if l.strip()]
    valid = [l for l in requested if l in available_labels]
    skipped = [l for l in requested if l not in available_labels]
    if skipped:
        print(f"  WARNING: labels not available: {skipped}")
    if not valid:
        print("  ERROR: no valid snapshots to fetch. Check --snapshots argument.")
        sys.exit(1)
    print(f"  Will fetch: {valid}")

    print(f"\nLoading passive tree from {TREE_PATH}...")
    tree_nodes = load_tree_nodes()
    print(f"  {len(tree_nodes)} nodes loaded")

    print(f"\nFetching heatmap: {args.skill} / {args.ascendancy}")
    avg_pcts, active_avg_pcts, support_avg_pcts, total_builds = aggregate_snapshots(
        snapshot, snapshot_name, args.ascendancy, args.skill, valid
    )

    if not avg_pcts:
        print("\nERROR: no data fetched.")
        sys.exit(1)

    # Separate into main tree nodes and ascendancy nodes
    main_nodes: list[tuple[int, float]] = []
    asc_nodes:  list[tuple[int, float]] = []
    notable_nodes: list[tuple[int, float]] = []

    for ggg_id, pct in avg_pcts.items():
        node = tree_nodes.get(ggg_id)
        if node is None:
            continue
        if node.get("Ascendancy"):
            if node.get("Name", ""):
                asc_nodes.append((ggg_id, pct))
        else:
            main_nodes.append((ggg_id, pct))
            if node.get("Type") == 1 and node.get("Name", ""):
                notable_nodes.append((ggg_id, pct))

    main_nodes.sort(key=lambda x: -x[1])
    asc_nodes.sort(key=lambda x: -x[1])
    notable_nodes.sort(key=lambda x: -x[1])

    exp = args.experience_level
    snapshot_label = "days 1-14" if exp == "league_starter" else "week 3+"

    # ── Text report ──────────────────────────────────────────────────────────
    lines = []
    lines.append("=" * 60)
    lines.append(f"  PASSIVE TREE — {args.ascendancy} [{args.skill}] ({exp})")
    lines.append(f"  Builds analysed: {total_builds}  [{snapshot_label}]")
    lines.append(f"  Source: poe.ninja heatmap API")
    lines.append("=" * 60)

    lines.append(f"\n--- TOP {args.top_notables} NOTABLE NODES ---")
    for nid, pct in notable_nodes[:args.top_notables]:
        name = tree_nodes.get(nid, {}).get("Name", "")
        lines.append(f"  {pct:>5.1f}%  [{nid}]  {name}")

    lines.append("\n--- ASCENDANCY NODES ---")
    for nid, pct in asc_nodes[:20]:
        name = tree_nodes.get(nid, {}).get("Name", "")
        lines.append(f"  {pct:>5.1f}%  [{nid}]  {name}")

    report = "\n".join(lines)
    print(f"\n{report}")

    # ── Output files ─────────────────────────────────────────────────────────
    # Filename includes the ascendancy so two ascendancies playing the same skill
    # (e.g. Lightning Arrow on Deadeye and Amazon) don't overwrite each other's report.
    from util import slug_for_skill
    skill_slug = slug_for_skill(args.skill)
    asc_slug   = args.ascendancy.lower()
    base_slug  = f"{skill_slug}_{asc_slug}_{exp}_passives"

    txt_path  = os.path.join(REPORT_DIR, f"{base_slug}.txt")
    json_path = os.path.join(REPORT_DIR, f"{base_slug}.json")

    if not args.skip_passives:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report)

        top_nodes_out = [
            {"id": nid, "pct": round(pct, 1), "count": round(pct * total_builds / 100),
             "name": tree_nodes.get(nid, {}).get("Name", "")}
            for nid, pct in main_nodes[:300]
        ]
        top_notables_out = [
            {"id": nid, "name": tree_nodes.get(nid, {}).get("Name", ""),
             "pct": round(pct, 1), "count": round(pct * total_builds / 100)}
            for nid, pct in notable_nodes[:args.top_notables]
        ]
        top_asc_out = [
            {"id": nid, "name": tree_nodes.get(nid, {}).get("Name", ""),
             "pct": round(pct, 1), "count": round(pct * total_builds / 100)}
            for nid, pct in asc_nodes[:20]
        ]

        json_data = {
            "ascendancy":       args.ascendancy,
            "skill":            args.skill,
            "experience_level": exp,
            "builds_analysed":  total_builds,
            "snapshot_group":   snapshot_label,
            "source":           "poe.ninja heatmap API",
            "snapshots_used":   valid,
            "top_nodes":        top_nodes_out,
            "top_notables":     top_notables_out,
            "top_asc_nodes":    top_asc_out,
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        print(f"\nText report : {txt_path}")
        print(f"JSON report : {json_path}")
    else:
        print("\n[--skip-passives] Passive reports not written.")

    # ── Gems report — per-skill support queries with lift scoring ────────────
    if active_avg_pcts and not args.skip_gems:
        actives_sorted = sorted(active_avg_pcts.items(), key=lambda x: -x[1])
        top_actives    = actives_sorted[:9]  # max 9 active skills

        # Primary query support baseline (used for lift calculation)
        primary_supports = support_avg_pcts  # from the main LA query

        print(f"\n--- TOP ACTIVE SKILLS (querying supports per skill) ---")
        skill_gems_out = []
        for skill_name, skill_pct in top_actives:
            print(f"\n  Fetching supports for: {skill_name} ({skill_pct:.1f}%)")
            _, _, skill_supports, _ = aggregate_snapshots(
                snapshot, snapshot_name, args.ascendancy, skill_name, valid
            )

            if skill_name == args.skill:
                # Primary skill: sort by raw adoption %
                ranked = sorted(skill_supports.items(), key=lambda x: -x[1])[:6]
            else:
                # Secondary skills: lift = skill_pct / primary_pct
                # High lift → support is disproportionately common in this skill's slot
                lift_data = []
                for sup_name, sup_pct in skill_supports.items():
                    primary_pct = primary_supports.get(sup_name, 1.0)
                    lift = sup_pct / max(primary_pct, 1.0)
                    lift_data.append((sup_name, sup_pct, lift))
                # Sort by lift descending — supports with high lift are slot-specific
                lift_data.sort(key=lambda x: -x[2])
                ranked = [(n, p) for n, p, _ in lift_data[:6]]

            print(f"    Supports: {', '.join(f'{n} {p:.0f}%' for n, p in ranked)}")
            skill_gems_out.append({
                "name":     skill_name,
                "pct":      round(skill_pct, 1),
                "supports": [
                    {"name": n, "pct": round(p, 1)}
                    for n, p in ranked
                ],
            })

        gems_slug = f"{skill_slug}_{exp}_gems"
        gems_path = os.path.join(REPORT_DIR, f"{gems_slug}.json")
        gems_data = {
            "ascendancy":       args.ascendancy,
            "skill":            args.skill,
            "experience_level": exp,
            "builds_analysed":  total_builds,
            "snapshot_group":   snapshot_label,
            "source":           "poe.ninja heatmap API",
            "snapshots_used":   valid,
            "skill_gems":       skill_gems_out,
        }
        with open(gems_path, "w", encoding="utf-8") as f:
            json.dump(gems_data, f, indent=2)
        print(f"\nGems report : {gems_path}")
    elif args.skip_gems:
        print("\n[--skip-gems] Gem report not written.")

    print(f"\nDone. {total_builds} builds, {len(main_nodes)} main-tree nodes, "
          f"{len(notable_nodes)} notables, {len(asc_nodes)} asc nodes.")


if __name__ == "__main__":
    main()
