"""
Pipeline Preview Tool
---------------------
Show what the pipeline WOULD do for a (skill, ascendancy) combo without actually
running it. Queries poe.ninja directly for current build counts across snapshots,
applies the bucket rules, and predicts viable code yields.

Usage:
  # Single combo (detailed output)
  python preview_combo.py --skill "Pounce" --ascendancy "Witchhunter"

  # Batch (summary table, one row per combo)
  python preview_combo.py --batch combos_to_check.txt

Batch file format — one combo per line, lines starting with # are comments:
  Pounce / Witchhunter
  Lightning Arrow / Deadeye
  Spark / Stormweaver
  # this is a comment
"""

import sys
import re
import json
import time
import random
import argparse
import urllib.request
import urllib.parse
import gzip
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Bucket thresholds (must match run_pipeline.py / future production rules) ──
MIN_BUILDS         = 50    # floor — below this, combo isn't discovered at all
LS_POPULAR_MIN     = 90    # ≥ this in LS discovery → popular LS
LS_EXOTIC_MIN      = 50    # 50..89 → exotic LS
EG_POPULAR_MIN     = 150   # ≥ this in EG discovery → popular EG
EG_EXOTIC_MIN      = 60    # 60..149 → exotic EG

# Discovery labels (one snapshot picked per mode for the count)
LS_DISCOVERY_LABEL = "day-4"
EG_DISCOVERY_LABEL = "week-3"

# Scrape windows per bucket
LS_POB_SNAPSHOTS      = ["day-2", "day-3", "day-4"]
EG_POB_SNAPSHOTS      = ["week-2", "week-3", "week-4"]
# Exotic uses a wide pooled window — only triggered when no popular bucket exists
EXOTIC_POB_SNAPSHOTS  = ["day-4", "day-5", "day-6", "week-1", "week-2", "week-3", "week-4"]

# Yield estimates — viable PoB codes per raw character fetched.
#   HIGH: ~95% — calibrated against observed popular-meta scrapes at the API cap
#         (Toxic Growth 294/294, LA Deadeye ~95%, Spark Stormweaver ~95%,
#          Essence Drain Lich ~95%, Storm Wave Invoker ~95%)
#   LOW: ~20% — UNCALIBRATED, hand-wave guess. We have no reliable sub-meta scrape data
#         yet to anchor the low end. The first proper exotic-tier scrape (e.g.
#         Pounce/Witchhunter) will give us a real number — retune then.
YIELD_LOW   = 0.20   # unknown; placeholder for sub-meta combos
YIELD_HIGH  = 0.95   # endgame-mature, observed

REPORT_DIR         = os.path.join(os.path.dirname(__file__), "pob_codes", "reports")


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass
    return raw


def get_snapshot(league: str = "sc"):
    raw = fetch("https://poe.ninja/poe2/api/data/index-state")
    data = json.loads(raw)
    for snap in data.get("snapshotVersions", []):
        url    = snap.get("url", "")
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
            return snap["version"], snap["snapshotName"], snap.get("timeMachineLabels", [])
    raise RuntimeError(f"No snapshot for league '{league}'")


def extract_strings(data: bytes, min_len: int) -> list[str]:
    pattern = re.compile(
        rb"(?:[\x20-\x7e]"
        rb"|[\xc2-\xdf][\x80-\xbf]"
        rb"|[\xe0-\xef][\x80-\xbf]{2}"
        rb"|[\xf0-\xf4][\x80-\xbf]{3}"
        rb"){" + str(min_len).encode() + rb",}"
    )
    out = []
    for m in pattern.finditer(data):
        try:
            out.append(m.group().decode("utf-8"))
        except UnicodeDecodeError:
            out.append(m.group().decode("ascii", errors="ignore"))
    return out


def count_chars(snapshot: str, snapshot_name: str, skill: str, ascendancy: str, label: str) -> int:
    """Return number of characters returned by /search for this combo at this label."""
    skill_enc = urllib.parse.quote(skill.replace(" ", "+"), safe="+")
    asc_enc   = urllib.parse.quote(ascendancy, safe="")
    url = (
        f"https://poe.ninja/poe2/api/builds/{snapshot}/search"
        f"?timemachine={urllib.parse.quote(label)}"
        f"&class={asc_enc}"
        f"&skills={skill_enc}"
        f"&heatmap=true"
        f"&overview={snapshot_name}"
    )
    raw = fetch(url)
    name_pos = raw.find(b"name")
    acct_pos = raw.find(b"account", name_pos + 1)
    if name_pos == -1 or acct_pos == -1:
        return 0
    name_block = raw[name_pos + 4 : acct_pos]
    char_names = [
        n.rstrip("*") for n in extract_strings(name_block, 1)
        if n.rstrip("*") not in ("name", "account")
        and len(n.rstrip("*")) >= 2
        and any(c.isalpha() for c in n.rstrip("*"))
    ]
    return len(char_names)


def bucket_for(builds_count: int, mode: str) -> str:
    """Return 'popular' / 'exotic' / 'below_min' for a given count + mode."""
    if builds_count < MIN_BUILDS:
        return "below_min"
    if mode == "league_starter":
        return "popular" if builds_count >= LS_POPULAR_MIN else "exotic"
    elif mode == "endgame":
        return "popular" if builds_count >= EG_POPULAR_MIN else "exotic"
    return "unknown"


def estimate_viable(counts: dict[str, int], snapshots: list[str]) -> tuple[int, int, int]:
    """Estimate (raw_fetches, viable_low, viable_high) across the given snapshots.

    Observed: popular combos at the API cap have near-zero dedup between snapshots
    (different leaderboard rankings each day produce different char sets), so we treat
    total raw fetches ≈ unique chars. Yield range is wide because it depends on
    combo maturity which we can't infer from counts alone.
    """
    raw = sum(counts.get(s, 0) for s in snapshots)
    if raw == 0:
        return 0, 0, 0
    viable_low  = int(raw * YIELD_LOW)
    viable_high = int(raw * YIELD_HIGH)
    return raw, viable_low, viable_high


def existing_reports(skill: str, ascendancy: str) -> list[str]:
    """Return list of report files that already exist for this combo (any format)."""
    skill_slug = skill.lower().replace(" ", "_")
    asc_slug   = ascendancy.lower()
    if not os.path.isdir(REPORT_DIR):
        return []
    found = []
    for fname in sorted(os.listdir(REPORT_DIR)):
        if fname.startswith(skill_slug) and (
            f"_{asc_slug}_" in fname or fname.startswith(f"{skill_slug}_league_starter") or fname.startswith(f"{skill_slug}_endgame")
        ):
            found.append(fname)
    return found


def preview_combo(skill: str, ascendancy: str, snap_version: str, snap_name: str,
                  available_labels: list[str], delay_min: float, delay_max: float,
                  queried_labels: list[str]) -> dict:
    """Run a preview for a single combo. Returns a dict of results."""
    counts: dict[str, int] = {}
    for label in queried_labels:
        if label not in available_labels:
            counts[label] = 0
            continue
        try:
            counts[label] = count_chars(snap_version, snap_name, skill, ascendancy, label)
        except Exception as e:
            counts[label] = -1
            print(f"  ERROR {skill}/{ascendancy} @ {label}: {e}")
        time.sleep(random.uniform(delay_min, delay_max))

    ls_count = counts.get(LS_DISCOVERY_LABEL, 0)
    eg_count = counts.get(EG_DISCOVERY_LABEL, 0)
    ls_bucket = bucket_for(ls_count, "league_starter")
    eg_bucket = bucket_for(eg_count, "endgame")

    # Decide which scrape(s) to run based on bucket assignment.
    # Rule: popular buckets get their own scrape. Exotic ONLY triggers if no popular
    # bucket exists — single wide-window scrape (day-4..week-4) pools cross-mode data.
    scrapes = []  # list of (label, snapshots, low, high)

    if ls_bucket == "popular":
        _, lo, hi = estimate_viable(counts, LS_POB_SNAPSHOTS)
        scrapes.append(("LS popular", LS_POB_SNAPSHOTS, lo, hi))
    if eg_bucket == "popular":
        _, lo, hi = estimate_viable(counts, EG_POB_SNAPSHOTS)
        scrapes.append(("EG popular", EG_POB_SNAPSHOTS, lo, hi))

    # Exotic fallback: only if NO popular bucket exists
    has_popular = ls_bucket == "popular" or eg_bucket == "popular"
    has_exotic  = ls_bucket == "exotic"  or eg_bucket == "exotic"
    if not has_popular and has_exotic:
        _, lo, hi = estimate_viable(counts, EXOTIC_POB_SNAPSHOTS)
        scrapes.append(("Exotic", EXOTIC_POB_SNAPSHOTS, lo, hi))

    # UI section — wizard precedence: EG popular > LS popular > Exotic > not surfaced
    section, section_low, section_high = "Not surfaced", 0, 0
    for label, _, lo, hi in scrapes:
        if hi == 0:
            continue
        if label == "EG popular":
            section, section_low, section_high = "Endgame", lo, hi
            break
        if label == "LS popular" and section == "Not surfaced":
            section, section_low, section_high = "League Starter", lo, hi
        if label == "Exotic" and section == "Not surfaced":
            section, section_low, section_high = "Exotic", lo, hi

    return {
        "skill":         skill,
        "ascendancy":    ascendancy,
        "counts":        counts,
        "ls_count":      ls_count,
        "eg_count":      eg_count,
        "ls_bucket":     ls_bucket,
        "eg_bucket":     eg_bucket,
        "scrapes":       scrapes,
        "section":       section,
        "section_low":   section_low,
        "section_high":  section_high,
    }


def parse_batch_file(path: str) -> list[tuple[str, str]]:
    """Parse a batch file. Each line is 'Skill Name / Ascendancy' or 'Skill, Asc'."""
    combos = []
    with open(path, encoding="utf-8") as f:
        for line_num, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # Accept '/' or ',' as separators
            if "/" in line:
                parts = line.split("/", 1)
            elif "," in line:
                parts = line.split(",", 1)
            else:
                print(f"  WARNING: line {line_num} unparseable: {line!r}")
                continue
            skill = parts[0].strip()
            asc   = parts[1].strip()
            if skill and asc:
                combos.append((skill, asc))
    return combos


def main():
    p = argparse.ArgumentParser(description="Preview what the pipeline would do for a combo")
    p.add_argument("--skill",      help="Skill name (omit if using --batch)")
    p.add_argument("--ascendancy", help="Ascendancy name (omit if using --batch)")
    p.add_argument("--batch",      help="Path to a file listing combos to check, one per line")
    p.add_argument("--league",     default="sc", choices=["sc","ssf","hc","hcssf"])
    p.add_argument("--delay-min",  type=float, default=3.5, help="min seconds between API calls (default 3.5)")
    p.add_argument("--delay-max",  type=float, default=5.0, help="max seconds between API calls (default 5.0)")
    args = p.parse_args()

    if not args.batch and (not args.skill or not args.ascendancy):
        p.error("Provide either (--skill AND --ascendancy) or --batch")

    snap_version, snap_name, available_labels = get_snapshot(args.league)
    relevant = ["day-2", "day-3", "day-4", "day-5", "day-6",
                "week-1", "week-2", "week-3", "week-4", "week-5", "week-6"]
    queried = [l for l in relevant if l in available_labels]

    # ── Batch mode ──────────────────────────────────────────────────────────
    if args.batch:
        combos = parse_batch_file(args.batch)
        if not combos:
            print(f"No combos parsed from {args.batch}")
            return
        print(f"\nSnapshot: {snap_version} ({snap_name})")
        print(f"Querying {len(queried)} snapshots × {len(combos)} combos = {len(queried)*len(combos)} API calls")
        approx_seconds = len(combos) * len(queried) * (args.delay_min + args.delay_max) / 2
        print(f"Estimated time: ~{approx_seconds/60:.1f} min\n")

        results = []
        for i, (skill, asc) in enumerate(combos, 1):
            print(f"[{i}/{len(combos)}] {skill} / {asc}")
            r = preview_combo(skill, asc, snap_version, snap_name,
                              available_labels, args.delay_min, args.delay_max, queried)
            results.append(r)
            scrape_labels = ", ".join(s[0] for s in r['scrapes']) or "none"
            n_str = f"{r['section_low']}-{r['section_high']}" if r['section_high'] > 0 else "0"
            print(f"  → {r['section']}  (LS={r['ls_count']}/{r['ls_bucket']}, EG={r['eg_count']}/{r['eg_bucket']}, scrapes: {scrape_labels}, n≈{n_str})")

        # ── Summary table ──────────────────────────────────────────────────
        print(f"\n{'='*110}")
        print(f"  SUMMARY")
        print(f"{'='*110}")
        print(f"  {'Skill':<22} {'Ascendancy':<22} {'LS-d4':>6} {'EG-w3':>6} {'Scrapes':<22} {'Section':<14} {'n≈':>10}")
        print(f"  {'-'*22} {'-'*22} {'-'*6} {'-'*6} {'-'*22} {'-'*14} {'-'*10}")
        for r in results:
            n_str = f"{r['section_low']}-{r['section_high']}" if r['section_high'] > 0 else "—"
            scrape_labels = ", ".join(s[0] for s in r['scrapes']) or "—"
            print(f"  {r['skill'][:22]:<22} {r['ascendancy'][:22]:<22} {r['ls_count']:>6} {r['eg_count']:>6} {scrape_labels[:22]:<22} {r['section']:<14} {n_str:>10}")

        # Bucket distribution
        from collections import Counter
        section_counts = Counter(r['section'] for r in results)
        print(f"\n  Section distribution: " + ", ".join(f"{k}={v}" for k, v in section_counts.most_common()))
        return

    # ── Single combo mode (detailed output) ─────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  PREVIEW: {args.skill} / {args.ascendancy}  [league={args.league}]")
    print(f"{'='*70}\n")
    print(f"Snapshot: {snap_version} ({snap_name})")
    print(f"Querying {len(queried)} snapshots: {queried}\n")

    counts: dict[str, int] = {}
    print(f"  {'Snapshot':<10}{'chars':>8}")
    print(f"  {'-'*18}")
    for label in queried:
        try:
            c = count_chars(snap_version, snap_name, args.skill, args.ascendancy, label)
            counts[label] = c
            print(f"  {label:<10}{c:>8}")
        except Exception as e:
            print(f"  {label:<10}  ERROR: {e}")
            counts[label] = 0
        time.sleep(random.uniform(args.delay_min, args.delay_max))

    # ── Bucket assignments ──────────────────────────────────────────────────
    ls_count = counts.get(LS_DISCOVERY_LABEL, 0)
    eg_count = counts.get(EG_DISCOVERY_LABEL, 0)
    ls_bucket = bucket_for(ls_count, "league_starter")
    eg_bucket = bucket_for(eg_count, "endgame")

    print(f"\n{'─'*70}")
    print(f"  BUCKET ASSIGNMENTS")
    print(f"{'─'*70}")
    print(f"  LS discovery ({LS_DISCOVERY_LABEL}): {ls_count} builds → {ls_bucket.upper()}")
    print(f"  EG discovery ({EG_DISCOVERY_LABEL}): {eg_count} builds → {eg_bucket.upper()}")

    # ── Predicted scraping ──────────────────────────────────────────────────
    print(f"\n{'─'*70}")
    print(f"  WHAT THE PIPELINE WOULD DO")
    print(f"{'─'*70}")

    will_have_ls_report = ls_bucket in ("popular", "exotic")
    will_have_eg_report = eg_bucket in ("popular", "exotic")

    # Apply the bucket→scrape rules
    has_popular = ls_bucket == "popular" or eg_bucket == "popular"
    has_exotic  = ls_bucket == "exotic"  or eg_bucket == "exotic"
    skill_slug  = args.skill.lower().replace(" ", "_")
    asc_slug    = args.ascendancy.lower()

    scrapes_run = []  # tracked for the wizard section below

    if ls_bucket == "popular":
        raw, lo, hi = estimate_viable(counts, LS_POB_SNAPSHOTS)
        print(f"  LS popular scrape: {LS_POB_SNAPSHOTS}")
        print(f"    raw fetches: {raw}, estimated viable codes: {lo}-{hi}")
        print(f"    report: {skill_slug}_{asc_slug}_league_starter_*.json")
        scrapes_run.append(("League Starter", lo, hi))
    elif ls_bucket == "exotic":
        print(f"  LS exotic ({ls_count} builds): not scraped here — see Exotic pass below" if not has_popular else f"  LS exotic ({ls_count} builds): SKIPPED (a popular EG scrape will cover this combo)")
    else:
        print(f"  LS: SKIPPED (count {ls_count} < MIN_BUILDS={MIN_BUILDS})")

    if eg_bucket == "popular":
        raw, lo, hi = estimate_viable(counts, EG_POB_SNAPSHOTS)
        print(f"  EG popular scrape: {EG_POB_SNAPSHOTS}")
        print(f"    raw fetches: {raw}, estimated viable codes: {lo}-{hi}")
        print(f"    report: {skill_slug}_{asc_slug}_endgame_*.json")
        scrapes_run.append(("Endgame", lo, hi))
    elif eg_bucket == "exotic":
        print(f"  EG exotic ({eg_count} builds): not scraped here — see Exotic pass below" if not has_popular else f"  EG exotic ({eg_count} builds): SKIPPED (a popular LS scrape will cover this combo)")
    else:
        print(f"  EG: SKIPPED (count {eg_count} < MIN_BUILDS={MIN_BUILDS})")

    # Exotic fallback — only if no popular bucket
    if not has_popular and has_exotic:
        raw, lo, hi = estimate_viable(counts, EXOTIC_POB_SNAPSHOTS)
        print(f"  Exotic scrape (wide window): {EXOTIC_POB_SNAPSHOTS}")
        print(f"    raw fetches: {raw}, estimated viable codes: {lo}-{hi}")
        print(f"    report: {skill_slug}_{asc_slug}_exotic_*.json")
        scrapes_run.append(("Exotic", lo, hi))

    # ── Wizard prediction ───────────────────────────────────────────────────
    print(f"\n{'─'*70}")
    print(f"  WIZARD BEHAVIOUR")
    print(f"{'─'*70}")

    if not scrapes_run:
        print(f"  → NOT SURFACED  (both LS and EG below MIN_BUILDS={MIN_BUILDS})")
    else:
        # Precedence: Endgame > League Starter > Exotic
        order = {"Endgame": 0, "League Starter": 1, "Exotic": 2}
        scrapes_run.sort(key=lambda s: order.get(s[0], 99))
        primary = scrapes_run[0]
        backups = scrapes_run[1:]
        section, lo, hi = primary
        # Popular sections (LS / EG) always have enough data in practice to be full
        # confidence — math floor is ~50 viable even at threshold + worst-case yield.
        # Exotic always carries the limited-data caveat regardless of n.
        confidence = "limited data, treat as sketch" if section == "Exotic" else "full confidence"
        print(f"  → {section} section — {confidence}  (n≈{lo}-{hi})")
        for b_section, b_lo, b_hi in backups:
            print(f"    ({b_section} report kept as silent backup, n≈{b_lo}-{b_hi})")

    # ── Existing on-disk reports ────────────────────────────────────────────
    existing = existing_reports(args.skill, args.ascendancy)
    print(f"\n{'─'*70}")
    print(f"  EXISTING REPORTS ON DISK")
    print(f"{'─'*70}")
    if existing:
        for f in existing:
            print(f"  {f}")
    else:
        print(f"  (none)")

    print()


if __name__ == "__main__":
    main()
