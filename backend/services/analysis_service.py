"""Analyse a parsed PoB build against the scraped meta reports.

Three axes of analysis:
  - Gems:    compare user's supports for the main skill vs top-builds adoption %
  - Passives: compare user's allocated nodes vs top-builds adoption %
  - Gear:    threshold check (life, res, attribute, weapon damage floor) per slot

Each analyser returns its own dataclass. All comparisons key off:
  - the user's main skill (auto-detected or supplied)
  - the user's ascendancy (extracted from PoB)
  - the experience level (defaults to league_starter for league relevance)

Confidence per axis = min(1.0, builds_analysed / 50). Sub-meta combos (<50
builds) are flagged so the frontend can show a low-confidence banner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from services.report_loader import load_report as _load_report
from services.pob_parser import ParsedBuild


# ── Tunables ───────────────────────────────────────────────────────────────

# A support is "high-value" (red flag if missing) at >= this adoption %.
HIGH_VALUE_SUPPORT_PCT = 50.0
# Below this, we don't bother flagging absence.
LOW_VALUE_SUPPORT_PCT = 20.0
# A passive notable is "core" if this % of top builds take it.
CORE_NODE_PCT = 60.0
# A passive notable the user has, but <this % take, may be a refund candidate.
# Lower than the previous 10% — we only fire on truly off-meta picks now that
# we restrict to notables (small travel nodes are excluded by design).
UNUSUAL_NODE_PCT = 5.0
# Cap on findings per kind to keep the report scannable.
MAX_FINDINGS_PER_KIND = 6
# Confidence saturates at this many analysed builds.
CONFIDENCE_FLOOR_BUILDS = 50

# ARMOUR slots — base type provides defence, but the slot MUST also roll life
# or ES for the prefix to be pulling its weight. Flagging here is high-signal.
ARMOUR_SLOTS = {"Helmet", "Body Armour", "Gloves", "Boots"}
# ACCESSORY slots — life/ES rolls on jewellery are good but not required.
# Most PoE2 builds spread res/spirit/attribute here rather than life. We don't
# flag these slots for missing defence; they're a different optimisation lever.
ACCESSORY_SLOTS = {"Amulet", "Ring 1", "Ring 2", "Belt"}
# Slots that contribute to res coverage (we flag missing res on any of these
# as a yellow informational — players concentrate res to free up other slots,
# so missing res isn't always a mistake; just a heads-up).
RES_SLOTS = ARMOUR_SLOTS | ACCESSORY_SLOTS

# Regex for any "to maximum Life" style mod
_LIFE_RE = re.compile(r"\+?\d+\s+to\s+(maximum\s+)?Life", re.IGNORECASE)
# Regex for any "to maximum Energy Shield" mod — counted as a substitute defence
_ES_RE = re.compile(r"\+?\d+\s+to\s+(maximum\s+)?Energy\s+Shield", re.IGNORECASE)
# Resistance mod patterns
_RES_FIRE_RE = re.compile(r"to\s+Fire\s+Resistance", re.IGNORECASE)
_RES_COLD_RE = re.compile(r"to\s+Cold\s+Resistance", re.IGNORECASE)
_RES_LIGHTNING_RE = re.compile(r"to\s+Lightning\s+Resistance", re.IGNORECASE)
_RES_CHAOS_RE = re.compile(r"to\s+Chaos\s+Resistance", re.IGNORECASE)
_RES_ELEMENTAL_RE = re.compile(r"to\s+Elemental\s+Resistance", re.IGNORECASE)
_RES_ALL_RE = re.compile(r"to\s+all\s+Elemental\s+Resistance", re.IGNORECASE)
# Attribute mod patterns
_STR_RE = re.compile(r"to\s+Strength", re.IGNORECASE)
_DEX_RE = re.compile(r"to\s+Dexterity", re.IGNORECASE)
_INT_RE = re.compile(r"to\s+Intelligence", re.IGNORECASE)
_ALL_ATTR_RE = re.compile(r"to\s+all\s+Attributes", re.IGNORECASE)
# Weapon damage mod patterns (any of these = "the weapon contributes to damage")
_WPN_DMG_PATTERNS = [
    re.compile(r"increased\s+Physical\s+Damage", re.IGNORECASE),
    re.compile(r"adds\s+\d+\s+to\s+\d+\s+(Physical|Cold|Fire|Lightning|Chaos)\s+Damage", re.IGNORECASE),
    re.compile(r"increased\s+Elemental\s+Damage", re.IGNORECASE),
    re.compile(r"increased\s+Attack\s+Speed", re.IGNORECASE),
    re.compile(r"increased\s+Critical", re.IGNORECASE),
    re.compile(r"increased\s+Spell\s+Damage", re.IGNORECASE),
    re.compile(r"\+\d+%\s+to\s+(Critical|Damage)", re.IGNORECASE),
]


# ── Data shapes ────────────────────────────────────────────────────────────

@dataclass
class GemFinding:
    kind: str           # "missing_high_value" | "unusual" | "core_present"
    support: str
    meta_pct: float     # 0..100; for "unusual" this is the (low) adoption %
    severity: str       # "red" | "yellow" | "green"


@dataclass
class GemAnalysis:
    main_skill: str
    builds_analysed: int
    confidence: float
    user_supports: list[str] = field(default_factory=list)
    findings: list[GemFinding] = field(default_factory=list)
    available: bool = True
    message: str = ""    # human-readable error if available=False


@dataclass
class PassiveFinding:
    kind: str           # "missing_core" | "unusual" | "ascendancy_missing"
    node_id: int
    node_name: str
    meta_pct: float
    severity: str       # "red" | "yellow" | "green"


@dataclass
class PassiveAnalysis:
    builds_analysed: int
    confidence: float
    user_node_count: int = 0
    findings: list[PassiveFinding] = field(default_factory=list)
    available: bool = True
    message: str = ""


@dataclass
class GearFinding:
    slot: str
    kind: str           # "no_life" | "no_res" | "no_attribute" | "no_damage" | "no_defence"
    message: str        # human-readable
    severity: str       # "red" | "yellow"


@dataclass
class GearAnalysis:
    total_uncapped_res: dict[str, int]  # fire/cold/lightning approximate total
    findings: list[GearFinding] = field(default_factory=list)
    available: bool = True
    message: str = ""


@dataclass
class BuildAnalysis:
    skill: str
    ascendancy: str
    class_name: str
    level: int
    experience_level: str
    candidate_skills: list[str]
    gem: GemAnalysis
    passive: PassiveAnalysis
    gear: GearAnalysis


# ── Helpers ────────────────────────────────────────────────────────────────

def _confidence(builds_analysed: int) -> float:
    if builds_analysed <= 0:
        return 0.0
    return min(1.0, builds_analysed / CONFIDENCE_FLOOR_BUILDS)


def report_exists(skill: str, ascendancy: str, kind: str) -> bool:
    """Cheap check: does any *gems/passives/gear* report cover this combo?"""
    return _load_report(skill, ascendancy, kind) is not None


def auto_detect_main_skill(parsed: ParsedBuild) -> tuple[str | None, list[str]]:
    """Return (best_guess, all_candidates_with_data).

    best_guess: highest-confidence main skill = first candidate with a gems
    report for this ascendancy. Falls back to first candidate with ≥2 supports.
    all_candidates_with_data: candidates filtered to those we have data for,
    so the frontend can present a "we detected X — change?" picker.
    """
    candidates = parsed.candidate_main_skills(min_supports=2)
    if not candidates:
        return None, []

    with_data = [s for s in candidates if report_exists(s, parsed.ascendancy, "gems")]
    if with_data:
        return with_data[0], with_data
    # No reports — return the user's candidates so the UI can show "no data" honestly
    return candidates[0], candidates


# ── Gem analyser ───────────────────────────────────────────────────────────

def analyse_gems(parsed: ParsedBuild, main_skill: str) -> GemAnalysis:
    report = _load_report(main_skill, parsed.ascendancy, "gems")
    if report is None:
        return GemAnalysis(
            main_skill=main_skill,
            builds_analysed=0,
            confidence=0.0,
            available=False,
            message=f"No gems report yet for {main_skill} / {parsed.ascendancy}.",
        )

    builds_analysed = int(report.get("builds_analysed", 0))
    confidence = _confidence(builds_analysed)

    # Find the matching skill_gems entry (the report can contain multiple active skills)
    target_supports: dict[str, float] = {}
    for sg in report.get("skill_gems", []):
        if (sg.get("name") or "").lower() == main_skill.lower():
            for s in sg.get("supports", []):
                target_supports[s["name"]] = float(s.get("pct", 0))
            break

    user_supports = parsed.supports_for_skill(main_skill)
    user_set_lower = {s.lower() for s in user_supports}

    findings: list[GemFinding] = []
    # Missing high-value supports
    for name, pct in sorted(target_supports.items(), key=lambda kv: -kv[1]):
        if pct >= HIGH_VALUE_SUPPORT_PCT and name.lower() not in user_set_lower:
            findings.append(GemFinding(
                kind="missing_high_value", support=name, meta_pct=pct, severity="red",
            ))

    # Unusual supports the user has (low adoption or absent from the report entirely)
    for s in user_supports:
        meta_pct = target_supports.get(s, 0.0)
        # Match case-insensitive against the report
        for rn, rp in target_supports.items():
            if rn.lower() == s.lower():
                meta_pct = rp
                break
        if meta_pct < LOW_VALUE_SUPPORT_PCT:
            findings.append(GemFinding(
                kind="unusual", support=s, meta_pct=meta_pct, severity="yellow",
            ))

    return GemAnalysis(
        main_skill=main_skill,
        builds_analysed=builds_analysed,
        confidence=confidence,
        user_supports=user_supports,
        findings=findings,
    )


# ── Passive analyser ───────────────────────────────────────────────────────

def analyse_passives(parsed: ParsedBuild, main_skill: str) -> PassiveAnalysis:
    report = _load_report(main_skill, parsed.ascendancy, "passives")
    if report is None:
        return PassiveAnalysis(
            builds_analysed=0, confidence=0.0, available=False,
            message=f"No passives report yet for {main_skill} / {parsed.ascendancy}.",
        )

    builds_analysed = int(report.get("builds_analysed", 0))
    confidence = _confidence(builds_analysed)
    user_nodes: set[int] = set(parsed.allocated_nodes)

    missing_core: list[PassiveFinding] = []
    unusual: list[PassiveFinding] = []

    # ── Notables the user is missing ─────────────────────────────────
    # top_notables is sorted desc by adoption %. Walk until we drop below the
    # core threshold.
    for n in sorted(report.get("top_notables", []), key=lambda x: -float(x.get("pct", 0))):
        pct = float(n.get("pct", 0))
        if pct < CORE_NODE_PCT:
            break
        nid = int(n.get("id", 0))
        if nid and nid not in user_nodes:
            missing_core.append(PassiveFinding(
                kind="missing_core", node_id=nid, node_name=n.get("name", ""),
                meta_pct=pct, severity="red",
            ))

    # ── Notables the user has taken that few top builds take ────────
    # Critical fix: restrict "unusual" to entries in `top_notables` ONLY, not
    # `top_nodes` (which floods with small travel nodes — every Attribute /
    # Movement Speed / Evasion node has low individual adoption because top
    # builds path through different routes, but those aren't "mistakes").
    notable_pct: dict[int, dict] = {}
    for n in report.get("top_notables", []):
        try:
            notable_pct[int(n["id"])] = n
        except (KeyError, ValueError, TypeError):
            continue
    for nid in parsed.allocated_nodes:
        info = notable_pct.get(nid)
        if info is None:
            continue   # not a notable (or no top build took it) — skip silently
        pct = float(info.get("pct", 0))
        if pct <= UNUSUAL_NODE_PCT:
            unusual.append(PassiveFinding(
                kind="unusual", node_id=nid, node_name=info.get("name", ""),
                meta_pct=pct, severity="yellow",
            ))

    # Sort unusual by lowest pct first (most off-meta first), cap at MAX.
    unusual.sort(key=lambda f: f.meta_pct)
    findings = missing_core[:MAX_FINDINGS_PER_KIND] + unusual[:MAX_FINDINGS_PER_KIND]

    return PassiveAnalysis(
        builds_analysed=builds_analysed,
        confidence=confidence,
        user_node_count=len(parsed.allocated_nodes),
        findings=findings,
    )


# ── Gear threshold analyser ────────────────────────────────────────────────

def _mods_have(item: dict, patterns: list[re.Pattern]) -> bool:
    mods = item.get("mods", []) or []
    return any(any(p.search(m) for p in patterns) for m in mods)


def _item_has_life(item: dict) -> bool:
    return _mods_have(item, [_LIFE_RE])


def _item_has_es(item: dict) -> bool:
    return _mods_have(item, [_ES_RE])


def _item_has_defensive_stat(item: dict) -> bool:
    """True if the item carries any defensive layer mod (life OR ES).

    In PoE2 it's common for builds to scale ES instead of life, so flagging
    "no life" on an ES item produces false positives. We only flag the slot
    when *neither* defensive stat is present.
    """
    return _item_has_life(item) or _item_has_es(item)


def _item_res_contribution(item: dict) -> dict[str, int]:
    """Rough per-element res contribution. Picks up "+X% to Cold Resistance",
    "+X% to all Elemental Resistance", etc. Conservative — values not summed
    when ranges are present; presence-based with a default value."""
    out = {"fire": 0, "cold": 0, "lightning": 0, "chaos": 0}
    for m in item.get("mods", []) or []:
        num_match = re.search(r"\+?(\d+)\s*%", m)
        if not num_match:
            continue
        val = int(num_match.group(1))
        if _RES_ALL_RE.search(m):
            out["fire"] += val; out["cold"] += val; out["lightning"] += val
        elif _RES_ELEMENTAL_RE.search(m):
            # Elemental Resistance (single roll) — counts for one type, conservatively the highest gap
            out["fire"] += val
        elif _RES_FIRE_RE.search(m):
            out["fire"] += val
        elif _RES_COLD_RE.search(m):
            out["cold"] += val
        elif _RES_LIGHTNING_RE.search(m):
            out["lightning"] += val
        elif _RES_CHAOS_RE.search(m):
            out["chaos"] += val
    return out


def _item_has_attribute(item: dict) -> bool:
    return _mods_have(item, [_STR_RE, _DEX_RE, _INT_RE, _ALL_ATTR_RE])


def _item_has_weapon_damage(item: dict) -> bool:
    return _mods_have(item, _WPN_DMG_PATTERNS)


def analyse_gear_thresholds(parsed: ParsedBuild) -> GearAnalysis:
    findings: list[GearFinding] = []
    res_total = {"fire": 0, "cold": 0, "lightning": 0, "chaos": 0}
    # Track accessory-wide attribute presence — we aggregate this into a
    # single finding rather than firing per-slot (most builds don't roll
    # attributes on every accessory and per-slot was over-eager).
    accessory_count = 0
    accessory_with_attr = 0

    for slot, item in parsed.items.items():
        if not item:
            continue
        rarity = item.get("rarity", "").upper()
        # Skip unique items for life/res/attr checks — uniques have their own justification
        is_unique = rarity == "UNIQUE"

        # ── Defensive layer check (armour slots only) ────────────────
        # PoE2: only armour pieces are *expected* to roll life or ES as
        # a prefix. Jewellery/belt prefixes go to spirit/attr/res/etc.
        if slot in ARMOUR_SLOTS and not is_unique and not _item_has_defensive_stat(item):
            findings.append(GearFinding(
                slot=slot, kind="no_defence",
                message=f"{slot} has no Life or Energy Shield roll — likely a wasted prefix on an armour piece.",
                severity="red",
            ))

        # ── Resistance contribution ───────────────────────────────────
        if slot in RES_SLOTS:
            contrib = _item_res_contribution(item)
            for k in res_total:
                res_total[k] += contrib[k]
            if not is_unique and sum(contrib.values()) == 0:
                findings.append(GearFinding(
                    slot=slot, kind="no_res",
                    message=f"{slot} has no Resistance roll — fine if you've capped elsewhere, otherwise consider rerolling.",
                    severity="yellow",
                ))

        # ── Attribute presence (aggregated, not per-slot) ─────────────
        if slot in ACCESSORY_SLOTS and not is_unique:
            accessory_count += 1
            if _item_has_attribute(item):
                accessory_with_attr += 1

        # ── Weapon damage check ──────────────────────────────────────
        if slot in ("Weapon 1", "Weapon 2") and not is_unique and not _item_has_weapon_damage(item):
            findings.append(GearFinding(
                slot=slot, kind="no_damage",
                message=f"{slot} has no damage-related mod — likely your biggest single upgrade.",
                severity="red",
            ))

    # Aggregate attribute finding — only fire if NO accessory has any attribute roll
    if accessory_count >= 2 and accessory_with_attr == 0:
        findings.append(GearFinding(
            slot="Accessories", kind="no_attribute",
            message="None of your accessories have an Attribute roll — most builds need attributes from gear for skill/weapon requirements.",
            severity="yellow",
        ))

    return GearAnalysis(
        total_uncapped_res=res_total,
        findings=findings,
    )


# ── Top-level orchestrator ─────────────────────────────────────────────────

def analyse_build(parsed: ParsedBuild, main_skill: str | None = None,
                  experience_level: str = "league_starter") -> BuildAnalysis:
    """Run all three analysers and bundle into a single response.

    If main_skill is None, auto-detect via report-availability filter.
    """
    detected, candidates = auto_detect_main_skill(parsed)
    skill = main_skill or detected or ""

    gem = analyse_gems(parsed, skill) if skill else GemAnalysis(
        main_skill="", builds_analysed=0, confidence=0.0, available=False,
        message="Could not detect a main skill with linked supports in this build.",
    )
    passive = analyse_passives(parsed, skill) if skill else PassiveAnalysis(
        builds_analysed=0, confidence=0.0, available=False,
        message="No main skill detected.",
    )
    gear = analyse_gear_thresholds(parsed)

    return BuildAnalysis(
        skill=skill,
        ascendancy=parsed.ascendancy,
        class_name=parsed.class_name,
        level=parsed.level,
        experience_level=experience_level,
        candidate_skills=candidates,
        gem=gem,
        passive=passive,
        gear=gear,
    )
