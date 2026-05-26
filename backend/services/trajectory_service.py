"""
Build-trajectory detector
-------------------------
Classifies a (skill, ascendancy) combo into one of four trajectory types so
the build guide can be honest about whether the LS data is the "destination"
or just a stepping stone:

  - continuous   — combo appears in both league_starter AND endgame reports.
                   The level-bucket toggle already covers the upgrade ladder.
  - migration    — combo appears in LS but NOT in EG, AND the same skill name
                   shows up as a role=secondary skill in a popular EG combo
                   for the same ascendancy. We can name the destination
                   (e.g. Spark Stormweaver → CoC Comet Stormweaver, 86%).
  - niche_endgame — combo appears in LS, no EG counterpart, and no migration
                    signal anywhere. Most likely the build is still viable at
                    endgame but stays below our top-100 sampling threshold.
                    The LS data IS the canonical reference.
  - endgame_only — combo appears in EG but NOT in LS. Typically a planned
                   endgame build people respec into rather than league-start.

Detection runs entirely against the static report JSONs on disk — no DB or
network. Results are cached at module level so the lookup is free after the
first call.
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from functools import lru_cache

# Same dir layout the analysers write to
_REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "pob_codes", "reports")

# Migration thresholds — pulled out so they're easy to tune. The user said
# this will need iteration, so leaving knobs accessible.
#
# A "migration target" is the skill that the abandoned LS skill links into at
# endgame. We require:
#   - the source LS skill appears as a top-level `skill_gem` entry in an EG
#     report for the same ascendancy (NOT just a support inside one)
#   - role classified as 'secondary' — main/trigger/aura/utility don't
#     indicate a migration (they're the same build, different position)
#   - adoption >= MIGRATION_PCT_THRESHOLD — too low and we catch incidental
#     gem inclusion ("oh some Comet builds happen to also use Frost Bomb")
MIGRATION_PCT_THRESHOLD = 50.0

# Some skill_gem entries report >100% (e.g. when the same skill is linked in
# multiple skill groups inside one PoB). Clamp for display sanity.
PCT_DISPLAY_CAP = 100.0


@dataclass
class BuildTrajectory:
    """Returned to the API / frontend. type drives banner rendering."""
    type: str                      # "continuous" | "migration" | "niche_endgame" | "endgame_only"
    target_skill: str = ""         # populated for type=migration
    target_pct: float = 0.0        # adoption of the source skill inside the target combo


# ── Filesystem helpers ─────────────────────────────────────────────────────

def _ls_gear_report_path(skill_slug: str, asc_slug: str) -> str:
    return os.path.join(_REPORT_DIR, f"{skill_slug}_{asc_slug}_league_starter_gear.json")


def _eg_gear_report_path(skill_slug: str, asc_slug: str) -> str:
    return os.path.join(_REPORT_DIR, f"{skill_slug}_{asc_slug}_endgame_gear.json")


def _report_indicates_data(path: str) -> bool:
    """True when the file exists AND has a non-zero builds_analysed count.
    The Spectre/Companion 'no-data' reports we wrote on the failed LS retry
    have builds_analysed=0 — those should NOT count as 'combo exists'."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return (d.get("builds_analysed", 0) or 0) > 0
    except Exception:
        return False


# ── Migration index (built once, cached) ───────────────────────────────────

@lru_cache(maxsize=1)
def _build_migration_index() -> dict[str, list[dict]]:
    """
    Scan every endgame gem report and build:
        {ascendancy_lower: [
            {host_skill: "Comet", secondary_skill: "Spark", secondary_pct: 86.0},
            ...
        ]}

    Built lazily on first call, cached for process lifetime. ~131 file reads
    on first call, a fraction of a second.
    """
    index: dict[str, list[dict]] = {}
    for path in glob.glob(os.path.join(_REPORT_DIR, "*_endgame_gems.json")):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        asc = (d.get("ascendancy") or "").lower()
        host_skill = d.get("skill") or ""
        if not asc or not host_skill:
            continue
        for sg in d.get("skill_gems", []):
            # Only top-level skill_gem entries with role=secondary qualify.
            # That filters out the LS skill being merely linked-as-a-support
            # inside Cast on Critical etc., which isn't a migration signal.
            if sg.get("role") != "secondary":
                continue
            name = (sg.get("name") or "").strip()
            pct  = sg.get("pct", 0) or 0
            if not name or pct < MIGRATION_PCT_THRESHOLD:
                continue
            index.setdefault(asc, []).append({
                "host_skill":     host_skill,
                "secondary_skill": name,
                "secondary_pct":  min(float(pct), PCT_DISPLAY_CAP),
            })
    return index


def _find_migration_target(skill: str, ascendancy: str) -> dict | None:
    """Return the best migration candidate for an abandoned LS skill, or None."""
    skill_lc = skill.lower().strip()
    asc_lc   = ascendancy.lower().strip()
    candidates = [
        c for c in _build_migration_index().get(asc_lc, [])
        if c["secondary_skill"].lower() == skill_lc
    ]
    if not candidates:
        return None
    # Prefer the candidate with the highest secondary_pct (strongest signal).
    return max(candidates, key=lambda c: c["secondary_pct"])


# ── Public API ─────────────────────────────────────────────────────────────

def detect_trajectory(skill: str, ascendancy: str) -> BuildTrajectory | None:
    """
    Classify (skill, ascendancy) into a trajectory type. Returns None when
    neither LS nor EG data exists (caller should show the data_pending state).
    """
    if not skill or not ascendancy:
        return None
    from util import slug_for_skill
    skill_slug = slug_for_skill(skill)
    asc_slug   = ascendancy.lower()

    has_ls = _report_indicates_data(_ls_gear_report_path(skill_slug, asc_slug))
    has_eg = _report_indicates_data(_eg_gear_report_path(skill_slug, asc_slug))

    if not has_ls and not has_eg:
        return None
    if has_ls and has_eg:
        return BuildTrajectory(type="continuous")
    if has_eg:  # EG only
        return BuildTrajectory(type="endgame_only")

    # LS only — try to detect a migration target
    target = _find_migration_target(skill, ascendancy)
    if target:
        return BuildTrajectory(
            type="migration",
            target_skill=target["host_skill"],
            target_pct=target["secondary_pct"],
        )
    return BuildTrajectory(type="niche_endgame")


def clear_cache() -> None:
    """Drop the cached migration index — for hot-reload after re-running analyse_gems."""
    _build_migration_index.cache_clear()
