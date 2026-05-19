"""
Gem Tags Builder
-----------------
Queries the PoE2 wiki (poe2wiki.net) Semantic MediaWiki API to fetch
gem tags for all skills discovered by run_pipeline.py, then writes
them to gem_tags.json for use in tag-based deduplication.

Usage:
  python build_gem_tags.py               # fetch tags for all skills in pipeline.db
  python build_gem_tags.py --skill "Lightning Arrow"   # single skill
  python build_gem_tags.py --all         # fetch all skills from wiki directly
"""

import sys
import os
import json
import time
import random
import sqlite3
import argparse
import urllib.request
import urllib.parse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DB_PATH       = os.path.join(BASE_DIR, "pipeline.db")
GEM_TAGS_PATH = os.path.join(BASE_DIR, "gem_tags.json")

WIKI_API    = "https://www.poe2wiki.net/w/api.php"
POE2DB_BASE = "https://poe2db.tw/us"
DELAY_RANGE = (2.5, 5.0)  # between requests


# ── Wiki fetching ───────────────────────────────────────────────────────────────

def fetch(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PoEProfessor/1.0 (gem tag builder)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


import re

# Weapon URL slugs from poe2db href links → normalised tag name
WEAPON_SLUG_MAP = {
    "one_hand_maces":  "mace",
    "two_hand_maces":  "mace",
    "one_hand_swords": "sword",
    "two_hand_swords": "sword",
    "one_hand_axes":   "axe",
    "two_hand_axes":   "axe",
    "quarterstaves":   "quarterstaff",
    "spears":          "spear",
    "staves":          "staff",
    "bows":            "bow",
    "crossbows":       "crossbow",
    "wands":           "wand",
    "sceptres":        "sceptre",
    "flails":          "flail",
    "shields":         "shield",
    "claws":           "claw",
    "daggers":         "dagger",
}

# Plain-text weapon names that may appear after "Requires:" without a link
WEAPON_TEXT_MAP = {
    "one hand mace":  "mace",
    "two hand mace":  "mace",
    "one-hand mace":  "mace",
    "two-hand mace":  "mace",
    "one hand sword": "sword",
    "two hand sword": "sword",
    "one hand axe":   "axe",
    "two hand axe":   "axe",
    "quarterstaff":   "quarterstaff",
    "spear":          "spear",
    "staff":          "staff",
    "bow":            "bow",
    "crossbow":       "crossbow",
    "wand":           "wand",
    "sceptre":        "sceptre",
    "flail":          "flail",
    "shield":         "shield",
    "claw":           "claw",
    "dagger":         "dagger",
}


def _extract_weapon_tags(raw: str) -> list[str]:
    """
    Parse weapon requirements from poe2db HTML.
    poe2db uses relative hrefs like href="One_Hand_Maces" (no leading slash)
    inside <div class="requirements"> blocks.
    Returns a list of normalised weapon tag strings (e.g. ["mace"]).
    """
    found = set()

    # Method 1: only match links with class="ItemClasses" — these are the weapon
    # requirement links on poe2db (e.g. href="One_Hand_Maces" class="ItemClasses ...")
    for slug_match in re.finditer(r'class="ItemClasses[^"]*"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*class="ItemClasses', raw, re.IGNORECASE):
        href = (slug_match.group(1) or slug_match.group(2) or "").lower()
        slug_lower = href.split("/")[-1]
        if slug_lower in WEAPON_SLUG_MAP:
            found.add(WEAPON_SLUG_MAP[slug_lower])

    # Method 2: plain text "Requires: Quarterstaves" / "Requires: One Hand Maces"
    for req_match in re.finditer(r'[Rr]equires?[:\s]+([A-Za-z ,]+?)(?:<|\n|$)', raw):
        req_text = req_match.group(1).lower().strip()
        for weapon_text, tag in WEAPON_TEXT_MAP.items():
            if weapon_text in req_text:
                found.add(tag)

    return list(found)


def fetch_tags_poe2db(skill: str) -> list[str] | None:
    """
    Primary source: poe2db.tw — game data export, most complete tag coverage.
    Fetches the gem page and parses the tag chips from the HTML, plus weapon requirements.
    """
    slug = skill.replace(" ", "_")
    url  = f"{POE2DB_BASE}/{urllib.parse.quote(slug)}"
    try:
        raw  = fetch(url).decode("utf-8", errors="replace")
        # poe2db renders gem tags as spans/badges — look for them
        # Pattern: class="... gem-tag ..." or data-tag or similar
        # Also look for plain text tag lists like "Attack, AoE, Projectile"
        patterns = [
            r'gem[_-]tag[^>]*>([^<]+)<',           # <span class="gem-tag">Attack</span>
            r'data-tag="([^"]+)"',                  # data-tag="attack"
            r'"tags"\s*:\s*\[([^\]]+)\]',           # JSON: "tags": ["attack", ...]
            r'Tags?[:\s]+([A-Z][a-zA-Z,\s]+?)(?:\n|<|\|)',  # Tags: Attack, AoE, Projectile
        ]
        tags = []
        for pattern in patterns:
            matches = re.findall(pattern, raw, re.IGNORECASE)
            if matches:
                for m in matches:
                    parts = re.split(r'[,;"\']+', m)
                    for p in parts:
                        t = p.strip().strip('"\'').lower()
                        if t and len(t) > 1 and len(t) < 30:
                            tags.append(t)
                if len(tags) >= 2:
                    break  # found tags via this pattern, stop trying others

        # Always append weapon requirement tags regardless of whether gem tags were found
        weapon_tags = _extract_weapon_tags(raw)
        for wt in weapon_tags:
            if wt not in tags:
                tags.append(wt)

        if len(tags) >= 2:
            return list(dict.fromkeys(tags))  # dedupe, preserve order
    except Exception:
        pass
    return None


def fetch_tags_wiki_semantic(skill: str) -> list[str] | None:
    """Semantic MediaWiki API on poe2wiki.net."""
    params = urllib.parse.urlencode({
        "action": "ask",
        "query":  f"[[{skill}]]|?Has gem tag|?Gem tag|?gem tag",
        "format": "json",
    })
    try:
        raw  = fetch(f"{WIKI_API}?{params}")
        data = json.loads(raw)
        for page_data in data.get("query", {}).get("results", {}).values():
            for key in ("Has gem tag", "Gem tag", "gem tag"):
                tags = page_data.get("printouts", {}).get(key, [])
                if tags:
                    return [
                        t.get("fulltext", t) if isinstance(t, dict) else str(t)
                        for t in tags
                    ]
    except Exception:
        pass
    return None


def fetch_tags_wiki_page(skill: str) -> list[str] | None:
    """Fallback: parse raw wiki markup for gem_tags field."""
    params = urllib.parse.urlencode({
        "action":  "query",
        "titles":  skill,
        "prop":    "revisions",
        "rvprop":  "content",
        "rvslots": "main",
        "format":  "json",
    })
    try:
        raw  = fetch(f"{WIKI_API}?{params}")
        data = json.loads(raw)
        for page in data.get("query", {}).get("pages", {}).values():
            if "missing" in page:
                return None
            content = (
                page.get("revisions", [{}])[0]
                    .get("slots", {}).get("main", {}).get("*", "")
                or page.get("revisions", [{}])[0].get("*", "")
            )
            for pattern in [
                r"\|\s*gem[_\s]tags?\s*=\s*([^\n\|}{]+)",
                r"\|\s*tags?\s*=\s*([^\n\|}{]+)",
            ]:
                m = re.search(pattern, content, re.IGNORECASE)
                if m:
                    tags = [t.strip().lower() for t in re.split(r"[,;]+", m.group(1)) if t.strip()]
                    if len(tags) >= 2:
                        return tags
    except Exception:
        pass
    return None


def fetch_gem_tags(skill: str) -> list[str] | None:
    """Try poe2db first (most complete), then wiki semantic, then wiki page."""
    tags = fetch_tags_poe2db(skill)
    if tags:
        return tags
    time.sleep(random.uniform(1.5, 3.0))

    tags = fetch_tags_wiki_semantic(skill)
    if tags:
        return [t.lower() for t in tags]
    time.sleep(random.uniform(1.5, 3.0))

    tags = fetch_tags_wiki_page(skill)
    return tags


# ── Main ────────────────────────────────────────────────────────────────────────

def load_gem_tags() -> dict[str, list[str]]:
    if os.path.exists(GEM_TAGS_PATH):
        with open(GEM_TAGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_gem_tags(tags: dict[str, list[str]]):
    with open(GEM_TAGS_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(tags.items())), f, indent=2)
    print(f"Saved {len(tags)} entries to gem_tags.json")


def get_skills_from_db() -> list[str]:
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT DISTINCT skill FROM combos ORDER BY skill").fetchall()
    conn.close()
    return [r[0] for r in rows]


# PoB weapon type names → our normalised tag
POB_WEAPON_TAG_MAP = {
    "Bow":                      "bow",
    "Crossbow":                 "crossbow",
    "Spear":                    "spear",
    "Flail":                    "flail",
    "Staff":                    "quarterstaff",  # PoB "Staff" = PoE2 Quarterstaff
    "Wand":                     "wand",
    "Claw":                     "claw",
    "Dagger":                   "dagger",
    "One Hand Axe":             "axe",
    "Two Hand Axe":             "axe",
    "One Hand Mace":            "mace",
    "Two Hand Mace":            "mace",
    "One Hand Sword":           "sword",
    "Two Hand Sword":           "sword",
    "Thrusting One Hand Sword": "sword",
    # "None" = unarmed, "Talisman" = ignore
}

POB_SKILLS_DIR = os.path.join(BASE_DIR, "..", "..", "..", "Downloads",
                              "PathOfBuilding-PoE2-dev", "PathOfBuilding-PoE2-dev",
                              "src", "Data", "Skills")


def parse_pob_weapon_types(pob_skills_dir: str) -> dict[str, list[str]]:
    """
    Parse all Skills/*.lua files from PoB and return a mapping of
    skill display name → list of normalised weapon tags (e.g. ["bow"]).
    Skills that work with any weapon (very long weaponTypes list) or have
    no weaponTypes block are returned with an empty list.
    """
    skill_weapons: dict[str, list[str]] = {}

    lua_files = [
        os.path.join(pob_skills_dir, f)
        for f in os.listdir(pob_skills_dir)
        if f.endswith(".lua") and not f.startswith("sup_")
    ]

    # Pattern: capture skill display name and its weaponTypes block
    skill_block_re = re.compile(
        r'\["[^"]+"\]\s*=\s*\{.*?name\s*=\s*"([^"]+)".*?weaponTypes\s*=\s*\{([^}]+)\}',
        re.DOTALL
    )
    weapon_entry_re = re.compile(r'\["([^"]+)"\]\s*=\s*true')

    for path in lua_files:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read()

        for m in skill_block_re.finditer(content):
            display_name  = m.group(1)
            weapon_block  = m.group(2)
            pob_types     = weapon_entry_re.findall(weapon_block)
            tags = []
            seen = set()
            for wt in pob_types:
                tag = POB_WEAPON_TAG_MAP.get(wt)
                if tag and tag not in seen:
                    tags.append(tag)
                    seen.add(tag)
            skill_weapons[display_name] = tags

    return skill_weapons


def apply_pob_weapon_tags(gem_tags: dict, pob_skills_dir: str) -> int:
    """
    Patch gem_tags in-place with weapon tags read from PoB Skills lua files.
    Returns the number of skills updated.
    """
    print(f"Parsing PoB Skills lua files from: {pob_skills_dir}")
    pob_map = parse_pob_weapon_types(pob_skills_dir)
    print(f"  Found {len(pob_map)} skill definitions in PoB")

    updated = 0
    for skill, tags in gem_tags.items():
        pob_weapons = pob_map.get(skill, [])
        if not pob_weapons:
            continue
        existing = set(tags)
        new_tags = [w for w in pob_weapons if w not in existing]
        if new_tags:
            gem_tags[skill] = tags + new_tags
            print(f"  {skill}: added weapon tags {new_tags}")
            updated += 1

    return updated


def main():
    parser = argparse.ArgumentParser(description="Build gem_tags.json from PoE2 wiki")
    parser.add_argument("--skill",    help="Fetch tags for a single skill only")
    parser.add_argument("--all",      action="store_true", help="Re-fetch all, even if already in file")
    parser.add_argument("--from-pob", metavar="PATH", nargs="?", const=POB_SKILLS_DIR,
                        help="Patch weapon tags from PoB Skills lua files (fast, no scraping). "
                             "Optionally specify path to PoB Skills/ dir.")
    args = parser.parse_args()

    gem_tags = load_gem_tags()
    print(f"Loaded {len(gem_tags)} existing entries from gem_tags.json")

    # Fast path: patch weapon tags from local PoB data, then exit
    if args.from_pob:
        pob_dir = args.from_pob
        if not os.path.isdir(pob_dir):
            print(f"PoB Skills directory not found: {pob_dir}")
            print("Pass the correct path: --from-pob \"C:/path/to/PathOfBuilding/src/Data/Skills\"")
            sys.exit(1)
        updated = apply_pob_weapon_tags(gem_tags, pob_dir)
        print(f"\nUpdated weapon tags for {updated} skills")
        save_gem_tags(gem_tags)
        return

    if args.skill:
        skills = [args.skill]
    else:
        db_skills  = get_skills_from_db()
        # When --all is set, also include everything already in gem_tags.json
        # so we refresh weapon tags for the full existing set, not just pipeline.db
        if args.all:
            all_skills = sorted(set(db_skills) | set(gem_tags.keys()))
            skills = all_skills
            print(f"Found {len(db_skills)} skills in pipeline.db + {len(gem_tags)} in gem_tags.json = {len(skills)} unique skills to refresh")
        else:
            skills = db_skills
            if not skills:
                print("No skills found in pipeline.db. Run run_pipeline.py --discover first.")
                print("Or use --skill 'Skill Name' to fetch a single skill.")
                sys.exit(1)
            print(f"Found {len(skills)} skills in pipeline.db")

    # Filter to skills we don't have tags for yet (unless --all)
    if not args.all:
        missing = [s for s in skills if s not in gem_tags]
        print(f"{len(missing)} skills missing tags (use --all to re-fetch everything)")
        skills = missing

    if not skills:
        print("All skills already have tags. Done.")
        return

    found = 0
    failed = []

    for i, skill in enumerate(skills, 1):
        print(f"\n[{i}/{len(skills)}] {skill}")
        tags = fetch_gem_tags(skill)

        if tags:
            weapon_tags = [t for t in tags if t in set(WEAPON_SLUG_MAP.values())]
            weapon_str  = f"  Weapon: {weapon_tags}" if weapon_tags else "  Weapon: none detected"
            print(f"  Tags:   {tags}")
            print(weapon_str)
            gem_tags[skill] = tags
            found += 1
            # Save after each successful fetch so progress isn't lost
            save_gem_tags(gem_tags)
        else:
            print(f"  Not found on wiki")
            failed.append(skill)

        if i < len(skills):
            time.sleep(random.uniform(*DELAY_RANGE))

    print(f"\nDone — {found} tags fetched, {len(failed)} not found")
    if failed:
        print("Not found on wiki (add manually to gem_tags.json):")
        for s in failed:
            print(f"  {s}")


if __name__ == "__main__":
    main()
