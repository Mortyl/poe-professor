"""
PoE Ninja Build Scraper
-----------------------
Fetches PoB export codes from poe.ninja for a given skill + ascendancy.
Supports poe.ninja's Time Machine to collect builds from multiple points
in the league, giving a much larger and more representative dataset.

Usage (latest snapshot only):
  python scrape_poeninja.py --skill "Lightning Arrow" --ascendancy Deadeye

Usage (early-league builds — days 1/3 + weeks 1-4):
  python scrape_poeninja.py --skill "Lightning Arrow" --ascendancy Deadeye --snapshots day-1,day-3,week-1,week-2,week-3,week-4

Usage (specific league):
  python scrape_poeninja.py --skill "Lightning Arrow" --ascendancy Deadeye --league hc --snapshots week-1,week-2

Then run the analyser:
  python analyse_builds.py --filter-class Ranger --filter-asc Deadeye
"""

import sys
import urllib.request
import urllib.parse
import json
import re
import gzip
import time
import os
import argparse
import base64
import zlib
import xml.etree.ElementTree as ET

# Force UTF-8 output so non-ASCII character names don't crash on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POB_DIR = os.path.join(os.path.dirname(__file__), "pob_codes")

# Delay in seconds between successful code fetches — conservative to avoid 429s
CHAR_DELAY        = 2.0
# Short delay after a no-code/404 response (doesn't stress the API)
NO_CODE_DELAY     = 0.5
# Extra pause between switching to a new time-machine snapshot
SNAPSHOT_DELAY    = 10.0


def decode_pob(code: str) -> bytes | None:
    code = code.strip().replace("-", "+").replace("_", "/")
    pad = 4 - len(code) % 4
    if pad != 4:
        code += "=" * pad
    try:
        return zlib.decompress(base64.b64decode(code))
    except Exception:
        return None


def has_skill_with_supports(xml_bytes: bytes, skill: str, min_supports: int = 3) -> bool:
    """Return True if the build has the given skill linked to at least min_supports support gems."""
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


def fetch(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_with_retry(url: str, max_retries: int = 4, base_delay: float = 3.0) -> bytes | None:
    """Fetch with exponential backoff on 429/5xx errors."""
    for attempt in range(max_retries):
        try:
            return fetch(url)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = base_delay * (2 ** attempt)
                print(f"    429 rate-limited — waiting {wait:.0f}s...")
                time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                print(f"    HTTP {e.code} — skipping")
                return None
        except Exception as e:
            print(f"    Error: {e}")
            return None
    print("    Max retries exceeded — skipping")
    return None


def get_snapshot(league: str = "sc") -> tuple[str, str, list[str]]:
    """
    Return (version, snapshot_name, available_time_machine_labels) for the league.
    Labels look like: "day-1", "day-3", "week-1", "week-2", etc.
    """
    data = json.loads(fetch("https://poe.ninja/poe2/api/data/index-state"))
    for snap in data.get("snapshotVersions", []):
        url = snap.get("url", "")
        is_hc  = "hc"  in url
        is_ssf = "ssf" in url
        # Exclude standard/private leagues
        if snap.get("overviewType", 0) != 0:
            continue
        match = (
            (league == "sc"    and not is_hc and not is_ssf and url not in ("standard",)) or
            (league == "ssf"   and     is_ssf and not is_hc) or
            (league == "hc"    and     is_hc  and not is_ssf) or
            (league == "hcssf" and     is_hc  and     is_ssf)
        )
        if match:
            labels = snap.get("timeMachineLabels", [])
            return snap["version"], snap["snapshotName"], labels
    raise RuntimeError(f"Could not find snapshot for league '{league}'")


def get_character_list(snapshot: str, snapshot_name: str, skill: str, ascendancy: str,
                       time_machine: str = "") -> list[tuple[str, str]]:
    """Return list of (character_name, account) pairs from the search endpoint."""
    skill_enc = urllib.parse.quote(skill)
    url = (
        f"https://poe.ninja/poe2/api/builds/{snapshot}/search"
        f"?overview={snapshot_name}&skill={skill_enc}&class={ascendancy}"
        f"&timeMachine={urllib.parse.quote(time_machine)}"
    )
    raw = fetch(url)

    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass

    # UTF-8-aware string extractor — parameterised by minimum run length
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

    # Use min_len=4 for the full scan (finds schema markers reliably)
    strings = extract_strings(raw, 4)

    try:
        name_idx    = strings.index("name")
        account_idx = strings.index("account")
    except ValueError:
        print("  WARNING: could not find 'name'/'account' markers in response")
        return []

    # Re-scan the name block with min_len=1 so short character names (< 4 chars)
    # aren't filtered out — a single missing name would shift every account pairing.
    name_marker_bytes    = b"name"
    account_marker_bytes = b"account"
    name_pos    = raw.find(name_marker_bytes)
    account_pos = raw.find(account_marker_bytes, name_pos + 1)

    if name_pos == -1 or account_pos == -1:
        print("  WARNING: could not locate name/account byte markers")
        return []

    name_block    = raw[name_pos + len(name_marker_bytes) : account_pos]
    account_block = raw[account_pos + len(account_marker_bytes) :]

    char_names    = [n.rstrip("*") for n in extract_strings(name_block, 3)
                     if n.rstrip("*") not in ("name", "account")]
    account_names = extract_strings(account_block, 4)

    schema_fields = {"class", "skills", "level", "life", "keypassives", "items", "mana"}
    trimmed: list[str] = []
    for a in account_names:
        if a.rstrip("*") in schema_fields:
            break
        trimmed.append(a.rstrip("*"))
    account_names = trimmed

    pairs = list(zip(char_names, account_names))
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for p in pairs:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    print(f"  Found {len(unique)} characters")
    return unique


def fetch_pob_code(snapshot: str, snapshot_name: str, account: str,
                   character: str, time_machine: str = "") -> str | None:
    """Fetch the PoB export code for a character at a given time-machine snapshot."""
    url = (
        f"https://poe.ninja/poe2/api/builds/{snapshot}/character"
        f"?account={urllib.parse.quote(account)}&name={urllib.parse.quote(character)}"
        f"&overview={snapshot_name}&timeMachine={urllib.parse.quote(time_machine)}"
    )
    raw = fetch_with_retry(url)
    if raw is None:
        return None
    try:
        return json.loads(raw).get("pathOfBuildingExport")
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Scrape PoB codes from poe.ninja")
    parser.add_argument("--skill",      default="Lightning Arrow",
                        help="Main skill name")
    parser.add_argument("--ascendancy", default="Deadeye",
                        help="Ascendancy name")
    parser.add_argument("--league",     default="sc",
                        help="League type: sc, ssf, hc, hcssf")
    parser.add_argument("--snapshots",  default="",
                        help="Comma-separated time-machine labels to fetch in addition to latest "
                             "(e.g. day-1,day-3,week-1,week-2,week-3,week-4). "
                             "Leave empty for current snapshot only.")
    parser.add_argument("--no-latest", action="store_true",
                        help="Skip the current/latest snapshot and only fetch the time-machine labels.")
    parser.add_argument("--append", action="store_true",
                        help="Append new codes to an existing JSONL file rather than overwriting. "
                             "Existing codes are loaded first so duplicates are never written twice.")
    args = parser.parse_args()

    os.makedirs(POB_DIR, exist_ok=True)

    print(f"Getting snapshot for [{args.league.upper()}]...")
    snapshot, snapshot_name, available_labels = get_snapshot(args.league)
    print(f"  Snapshot : {snapshot} ({snapshot_name})")
    print(f"  Available time-machine labels: {sorted(available_labels)}")

    # Build list of time-machine labels to fetch.
    requested_labels: list[str] = [] if args.no_latest else [""]
    if args.snapshots:
        for label in args.snapshots.split(","):
            label = label.strip()
            if label and label not in requested_labels:
                if label in available_labels:
                    requested_labels.append(label)
                else:
                    print(f"  WARNING: '{label}' not available for this league — skipping")

    print(f"\nWill fetch across {len(requested_labels)} snapshot(s): "
          f"{[l or 'latest' for l in requested_labels]}")

    # One file per skill+ascendancy+league — no _early suffix.
    # Snapshot tags on each JSONL line handle league_starter vs endgame filtering.
    slug      = f"{args.skill.lower().replace(' ', '_')}_{args.ascendancy.lower()}_{args.league}"
    out_path  = os.path.join(POB_DIR, f"{slug}.txt")
    jsonl_path = out_path.replace(".txt", ".jsonl")

    # Collect all codes, deduplicating on exact code string.
    # In append mode, seed all_codes from the existing JSONL so we never
    # write a code that's already in the file.
    all_codes: set[str] = set()
    ordered_codes: list[str] = []
    ordered_entries: list[dict] = []  # new entries only

    if args.append and os.path.exists(jsonl_path):
        print(f"\nAppend mode — loading existing codes from {jsonl_path}...")
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("code"):
                        all_codes.add(obj["code"])
                except json.JSONDecodeError:
                    continue
        print(f"  {len(all_codes)} existing codes loaded (will be skipped if seen again)")

    total_snapshots = len(requested_labels)

    for snap_idx, label in enumerate(requested_labels):
        label_display = label or "latest"
        print(f"\n{'='*60}")
        print(f"  Snapshot {snap_idx+1}/{total_snapshots}: {label_display}")
        print(f"{'='*60}")

        print(f"  Fetching character list for [{label_display}]...")
        pairs = get_character_list(snapshot, snapshot_name, args.skill, args.ascendancy, label)
        if not pairs:
            print("  No characters found for this snapshot — skipping.")
            continue

        total_chars = len(pairs)
        got = 0
        skipped = 0
        rejected = 0
        for i, (char_name, account) in enumerate(pairs):
            print(f"  [{i+1}/{total_chars}] {char_name} ({account})  [{label_display}]")
            code = fetch_pob_code(snapshot, snapshot_name, account, char_name, label)
            if code:
                if code in all_codes:
                    skipped += 1
                    print(f"    ~ duplicate — skipped")
                else:
                    # Verify the build actually has the target skill linked to 3+ supports.
                    # poe.ninja search can return builds that don't genuinely use the skill
                    # (e.g. Mercenary/grenadier builds appearing in a Deadeye LA search).
                    xml_bytes = decode_pob(code)
                    if xml_bytes and has_skill_with_supports(xml_bytes, args.skill, min_supports=3):
                        all_codes.add(code)
                        ordered_codes.append(code)
                        ordered_entries.append({"code": code, "snapshot": label_display})
                        got += 1
                        print(f"    + new code ({len(code)} chars)")
                    else:
                        rejected += 1
                        print(f"    - rejected (skill not found with 3+ supports)")
            else:
                print(f"    - no code")
            # Full delay only on success; rejected/404 responses don't stress the API
            time.sleep(CHAR_DELAY if code else NO_CODE_DELAY)

        print(f"\n  Snapshot done: {got} new codes, {skipped} duplicates, {rejected} rejected (wrong skill)")

        if snap_idx < total_snapshots - 1:
            print(f"  Pausing {SNAPSHOT_DELAY:.0f}s before next snapshot...")
            time.sleep(SNAPSHOT_DELAY)

    write_mode = "a" if args.append else "w"

    with open(out_path, write_mode, encoding="utf-8") as f:
        if ordered_codes:
            if args.append:
                f.write("\n")
            f.write("\n".join(ordered_codes))

    with open(jsonl_path, write_mode, encoding="utf-8") as f:
        for entry in ordered_entries:
            f.write(json.dumps({
                "code":       entry["code"],
                "snapshot":   entry["snapshot"],
                "skill":      args.skill,
                "ascendancy": args.ascendancy,
                "league":     args.league,
            }) + "\n")

    mode_label = "appended" if args.append else "saved"
    print(f"\n{'='*60}")
    print(f"  DONE — {len(ordered_codes)} new unique PoB codes {mode_label}")
    print(f"  File : {out_path}")
    print(f"  JSONL: {jsonl_path}")
    print(f"\nNow run:")
    print(f"  python analyse_passives.py --ascendancy {args.ascendancy} --experience-level league_starter")
    print(f"  python analyse_gem_links.py --skill \"{args.skill}\" --experience-level league_starter")


if __name__ == "__main__":
    main()
