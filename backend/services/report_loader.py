"""Tiny shared helper to load a scraped meta report by (skill, ascendancy, type).

Extracted from `build_service.py` so the analyser (and anything else) can
load reports without pulling in `dotenv` / Claude / other build_service
dependencies at import time.
"""

import json
import os

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "pob_codes", "reports")

# Experience-level precedence — endgame > league_starter > exotic.
REPORT_EXP_PRECEDENCE = ("endgame", "league_starter", "exotic")


def load_report(skill: str, ascendancy: str, report_type: str) -> dict | None:
    """Load a JSON report if it exists, trying most-specific → most-legacy filenames.

    For each experience level in precedence order, tries:
      1. {skill}_{ascendancy}_{exp}_{type}.json — current per-combo format
      2. {skill}_{exp}_{type}.json              — legacy skill-only
      3. {ascendancy}_{exp}_{type}.json         — ancient ascendancy-only fallback
    """
    from util import slug_for_skill
    skill_slug = slug_for_skill(skill)
    asc_slug = ascendancy.lower()

    for exp in REPORT_EXP_PRECEDENCE:
        candidates = [
            os.path.join(REPORT_DIR, f"{skill_slug}_{asc_slug}_{exp}_{report_type}.json"),
            os.path.join(REPORT_DIR, f"{skill_slug}_{exp}_{report_type}.json"),
            os.path.join(REPORT_DIR, f"{asc_slug}_{exp}_{report_type}.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
    return None
