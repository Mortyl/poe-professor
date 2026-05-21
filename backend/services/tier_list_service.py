"""Data-driven tier list of meta builds for the current league.

Pulls combos from `pipeline.db`, pairs each (skill, ascendancy) combo's
league_starter count with its endgame count, computes a composite score
that rewards builds that GREW from league start to endgame (retention),
then buckets into S/A/B/C/D within each archetype.

No accounts, no votes — pure adoption + retention. The user-voted half
of the tier list comes later, layered on top once accounts are in.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Iterable

# Reuse the archetype routing rules already used by /api/builds/browse so we
# don't fork classification logic between two endpoints.
from routers.builds import (
    _assign_archetype,
    _load_archetype_config,
    _load_gem_tags,
    _load_unique_driven_builds,
)
from services.report_loader import load_report

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "pipeline.db")

# Tier cutoffs: rank within an archetype as a fraction (1/N for best, 1.0 worst).
# A build at percentile <= 0.05 → S; <= 0.15 → A; <= 0.35 → B; <= 0.60 → C; rest → D.
_TIER_CUTOFFS: list[tuple[str, float]] = [
    ("S", 0.05),
    ("A", 0.15),
    ("B", 0.35),
    ("C", 0.60),
    ("D", 1.00),
]

# Below this many builds in an archetype we don't actually tier — we just show
# them as a flat sorted list with a "low sample size" note. Avoids "tier S =
# the one build we've scraped" silliness for niche archetypes.
_MIN_BUILDS_FOR_TIERING = 8

# Cap on how many builds we show in the B/C/D tiers. They're the long
# tail of an archetype — a fully-tiered Spell archetype puts ~11 in B,
# ~13 in C and ~21 in D, which is visual noise. Take the strongest 4 of
# each. S and A are uncapped (always small anyway — ~5% and ~10%).
_MAX_TAIL_TIER = 4
_CAPPED_TIERS = {"B", "C", "D"}


def _load_combo_counts(league: str) -> dict[tuple[str, str], dict]:
    """Return {(skill, ascendancy): {league_starter_count, endgame_count,
    tag_signature, variant_companion}} for the given league.

    Falls back gracefully if the DB hasn't been migrated to include the
    `mode` column yet (returns everything under league_starter).
    """
    if not os.path.exists(DB_PATH):
        return {}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        has_mode_col = any(
            r[1] == "mode" for r in conn.execute("PRAGMA table_info(combos)").fetchall()
        )

        out: dict[tuple[str, str], dict] = {}

        def _accumulate(rows: Iterable[sqlite3.Row], mode_key: str) -> None:
            for r in rows:
                key = (r["skill"], r["ascendancy"])
                if key not in out:
                    out[key] = {
                        "skill": r["skill"],
                        "ascendancy": r["ascendancy"],
                        "tag_signature": r["tag_signature"] or "",
                        "variant_companion": r["variant_companion"] or "",
                        "league_starter_count": 0,
                        "endgame_count": 0,
                    }
                # Newer rows can update tag_signature/variant if previously blank
                if r["tag_signature"] and not out[key]["tag_signature"]:
                    out[key]["tag_signature"] = r["tag_signature"]
                if r["variant_companion"] and not out[key]["variant_companion"]:
                    out[key]["variant_companion"] = r["variant_companion"]
                out[key][f"{mode_key}_count"] = r["builds_count"]

        if has_mode_col:
            for mode_key in ("league_starter", "endgame"):
                rows = conn.execute(
                    """SELECT skill, ascendancy, tag_signature, variant_companion, builds_count
                       FROM combos
                       WHERE builds_count > 0 AND mode = ?""",
                    (mode_key,),
                ).fetchall()
                _accumulate(rows, mode_key)
        else:
            # Pre-migration: everything counts as league_starter
            rows = conn.execute(
                """SELECT skill, ascendancy, tag_signature, variant_companion, builds_count
                   FROM combos
                   WHERE builds_count > 0"""
            ).fetchall()
            _accumulate(rows, "league_starter")
    finally:
        conn.close()

    return out


def _composite_score(starter: int, endgame: int) -> float:
    """Composite popularity-and-retention score.

    Base = max of the two snapshots (so an endgame-only build isn't penalised
    for not having a league_starter count, and vice versa).

    Retention bonus = up to +30% when the endgame share grew relative to
    league_starter share. The +30% cap stops a single tiny endgame build
    (eg. 2 → 10 = 5x growth) from leapfrogging a build with hundreds of
    players just on growth ratio.
    """
    base = max(starter, endgame)
    if base == 0:
        return 0.0
    if starter == 0 or endgame == 0:
        return float(base)
    ratio = endgame / starter
    # Map ratio: 1.0 → 0%, 2.0+ → +30%. Linear in between.
    bonus = max(0.0, min(0.30, (ratio - 1.0) * 0.30))
    return base * (1.0 + bonus)


def _bucket_into_tiers(sorted_builds: list[dict]) -> dict[str, list[dict]]:
    """Assign each build to S/A/B/C/D by its rank percentile within the list.

    B/C/D tiers are capped to _MAX_TAIL_TIER builds — the long-tail tiers
    would otherwise drown the page in low-priority picks.
    """
    tiers: dict[str, list[dict]] = {tier: [] for tier, _ in _TIER_CUTOFFS}
    n = len(sorted_builds)
    if n == 0:
        return tiers
    for rank, build in enumerate(sorted_builds):
        pct = (rank + 1) / n
        for tier, cutoff in _TIER_CUTOFFS:
            if pct <= cutoff:
                tiers[tier].append(build)
                break

    # Cap the long-tail tiers — sorted_builds is in score-desc order so the
    # first N within each tier are the strongest of that bucket.
    for capped_tier in _CAPPED_TIERS:
        tiers[capped_tier] = tiers[capped_tier][:_MAX_TAIL_TIER]
    return tiers


def build_tier_list(league: str = "sc", mode: str = "composite") -> dict:
    """Public entrypoint. mode ∈ {composite, league_starter, endgame}.

    The mode controls only how we *score* the builds for ranking; we always
    return both counts and the retention ratio in the response so the UI can
    show transparency on hover.
    """
    combos = _load_combo_counts(league)
    config = _load_archetype_config()
    gem_tags = _load_gem_tags()
    unique_driven = _load_unique_driven_builds()

    # 1. Score each combo + assign it to an archetype bucket
    archetype_buckets: dict[str, list[dict]] = {}
    archetype_meta: dict[str, dict] = {
        a["id"]: {"id": a["id"], "label": a["label"], "icon": a.get("icon", "")}
        for a in config["archetypes"]
    }

    for (skill, ascendancy), c in combos.items():
        starter = int(c.get("league_starter_count", 0) or 0)
        endgame = int(c.get("endgame_count", 0) or 0)

        if mode == "league_starter":
            score = float(starter)
        elif mode == "endgame":
            score = float(endgame)
        else:  # composite
            score = _composite_score(starter, endgame)

        if score <= 0:
            continue

        arch_id, _sub_id = _assign_archetype(
            skill=skill,
            tag_sig=c["tag_signature"],
            variant_companion=c["variant_companion"],
            gem_tags=gem_tags,
            config=config,
            ascendancy=ascendancy,
            unique_driven=unique_driven,
        )

        retention_ratio = (endgame / starter) if starter > 0 else None

        # `analysed` = at least one of {gems, gear, passives} reports exists on
        # disk for this combo. Lets the frontend grey out cards we can't yet
        # deep-link into without showing empty panels.
        analysed = any(
            load_report(skill, ascendancy, kind) is not None
            for kind in ("gems", "gear", "passives")
        )

        archetype_buckets.setdefault(arch_id, []).append({
            "skill": skill,
            "ascendancy": ascendancy,
            "starter_count": starter,
            "endgame_count": endgame,
            "score": round(score, 1),
            "retention_ratio": round(retention_ratio, 2) if retention_ratio is not None else None,
            "analysed": analysed,
        })

    # 2. Within each archetype, sort by score and bucket into tiers
    result_archetypes: list[dict] = []
    for arch in config["archetypes"]:
        arch_id = arch["id"]
        builds = archetype_buckets.get(arch_id, [])
        if not builds:
            continue
        builds.sort(key=lambda b: -b["score"])

        # Don't tier tiny archetypes — they get the flat sorted list with a flag
        if len(builds) < _MIN_BUILDS_FOR_TIERING:
            result_archetypes.append({
                **archetype_meta[arch_id],
                "tiered": False,
                "build_count": len(builds),
                "builds": builds,
                "tiers": {},
            })
            continue

        result_archetypes.append({
            **archetype_meta[arch_id],
            "tiered": True,
            "build_count": len(builds),
            "builds": [],  # tiered view doesn't need the flat list
            "tiers": _bucket_into_tiers(builds),
        })

    return {
        "league": league,
        "mode": mode,
        "total_combos": sum(a["build_count"] for a in result_archetypes),
        "archetypes": result_archetypes,
    }
