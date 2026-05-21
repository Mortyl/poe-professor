"""Build a canonical PoB code for a generated build guide.

Two-step approach ("Path C — surgical edit"):

  1. **Pick** the closest-matching scraped player PoB for this skill+ascendancy:
     filter to characters of decent level, score by passive-node overlap +
     support overlap with the guide's recommendations, prefer later snapshots.

  2. **Surgically rewrite** the `<Skill>` block for the main skill so its
     support gems match the guide's top supports. Other parts of the player's
     PoB (passive allocation, ascendancy, character settings, items, jewels,
     flasks) are left intact — we only override the bits the guide actually
     opines about.

The rewrite reuses gem `<Gem>` element templates lifted from the scraped
corpus, so injected supports keep correct `gemId`/`skillId`/`variantId`
metadata that PoB needs to resolve them on import.
"""

from __future__ import annotations

import base64
import json
import os
import re
import zlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable

POB_DIR = os.path.join(os.path.dirname(__file__), "..", "pob_codes")

# Snapshots we consider "early league" — under-cooked. We prefer later ones.
_EARLY_SNAPSHOTS = {"day-1", "day-2", "day-3"}
# Minimum character level we'll pick from. Lower than this, the build is too
# under-developed to be representative.
_MIN_LEVEL = 85

_NODES_RE = re.compile(r'<Spec\b[^>]*\bnodes="([^"]*)"')
_LEVEL_RE = re.compile(r'<Build\b[^>]*\blevel="(\d+)"')


@dataclass
class PobProvenance:
    """Lightweight metadata about which scraped build a PoB code came from.
    Surfaced to the frontend so users see they're getting a real player's
    build with the guide's supports patched in."""
    snapshot: str = ""
    level: int = 0
    node_overlap: int = 0
    support_overlap: int = 0
    supports_rewritten: bool = False


# ── Slug + decode helpers ──────────────────────────────────────────────────

def _jsonl_path(skill: str, ascendancy: str, league: str) -> str:
    slug = f"{skill.lower().replace(' ', '_')}_{ascendancy.lower()}_{league}"
    return os.path.join(POB_DIR, f"{slug}.jsonl")


def _decode(code: str) -> bytes | None:
    try:
        return zlib.decompress(base64.urlsafe_b64decode(code))
    except Exception:
        return None


def _encode(xml_bytes: bytes) -> str:
    """Re-encode XML → base64(url-safe) zlib. Matches the format PoB expects."""
    return base64.urlsafe_b64encode(zlib.compress(xml_bytes)).decode("ascii")


# ── Quick-scan extractors (avoid full XML parse during selection) ─────────

def _extract_nodes(xml: str) -> set[int]:
    m = _NODES_RE.search(xml)
    if not m:
        return set()
    return {int(t) for t in m.group(1).split(",") if t.strip().isdigit()}


def _extract_level(xml: str) -> int:
    m = _LEVEL_RE.search(xml)
    return int(m.group(1)) if m else 0


def _extract_supports_for_skill(xml_bytes: bytes, skill: str) -> set[str]:
    """Return the support gem names linked to the given main skill."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return set()
    skill_lower = skill.lower()
    out: set[str] = set()
    for sk in root.iter("Skill"):
        gems = [g for g in sk.findall("Gem")
                if g.attrib.get("enabled", "true") == "true"
                and g.attrib.get("nameSpec", "").strip()]
        if not gems:
            continue
        if gems[0].attrib.get("nameSpec", "").lower() == skill_lower:
            for g in gems[1:]:
                name = g.attrib.get("nameSpec", "").strip()
                if name:
                    out.add(name)
    return out


# ── Selection: pick the best-match scraped PoB ─────────────────────────────

def _score_candidate(node_overlap: int, support_overlap: int) -> int:
    """Each matched support is worth ~5 nodes — supports are the user-visible
    identity of the build."""
    return node_overlap + support_overlap * 5


def _pick_best_pob(
    path: str,
    target_nodes: set[int],
    target_supports: set[str],
    skill: str,
) -> tuple[str | None, PobProvenance]:
    """Stream the JSONL and pick the highest-scoring entry."""
    best_code: str | None = None
    best_score = -1
    best_prov = PobProvenance()
    # Soft-tier fallbacks so we still return *something* if no candidate
    # passes the level/snapshot filter.
    relaxed_best_code: str | None = None
    relaxed_best_score = -1
    relaxed_best_prov = PobProvenance()

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            code = entry.get("code")
            snapshot = entry.get("snapshot", "")
            if not isinstance(code, str):
                continue

            raw = _decode(code)
            if raw is None:
                continue
            xml = raw.decode("utf-8", errors="replace")

            nodes = _extract_nodes(xml)
            level = _extract_level(xml)
            supports = _extract_supports_for_skill(raw, skill) if target_supports else set()

            n_overlap = len(nodes & target_nodes) if target_nodes else len(nodes)
            s_overlap = len(supports & {s.lower(): s for s in target_supports} if False else supports & target_supports)
            score = _score_candidate(n_overlap, s_overlap)

            prov = PobProvenance(
                snapshot=snapshot,
                level=level,
                node_overlap=n_overlap,
                support_overlap=s_overlap,
            )

            # Always track best regardless of filter, as a relaxed fallback
            if score > relaxed_best_score:
                relaxed_best_score = score
                relaxed_best_code = code
                relaxed_best_prov = prov

            # Strict filter — what we'd prefer to return
            if level < _MIN_LEVEL:
                continue
            if snapshot in _EARLY_SNAPSHOTS:
                continue
            if score > best_score:
                best_score = score
                best_code = code
                best_prov = prov

    if best_code:
        return best_code, best_prov
    # Fall back to the relaxed best so we still emit *something* useful.
    return relaxed_best_code, relaxed_best_prov


# ── Surgical skill-block rewrite ───────────────────────────────────────────

def _build_gem_template_index(path: str) -> dict[str, dict]:
    """Scan all PoBs in a JSONL once and collect `<Gem>` attribute templates,
    keyed by lowercase nameSpec. First-seen wins. Used to fill in PoB metadata
    (gemId/skillId/variantId) when injecting a new support."""
    templates: dict[str, dict] = {}
    try:
        f = open(path, encoding="utf-8")
    except OSError:
        return templates
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            code = entry.get("code")
            if not isinstance(code, str):
                continue
            raw = _decode(code)
            if raw is None:
                continue
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                continue
            for g in root.iter("Gem"):
                name = (g.attrib.get("nameSpec") or "").strip()
                if name and name.lower() not in templates:
                    templates[name.lower()] = dict(g.attrib)
    return templates


_MINIMAL_GEM_ATTRS = {
    "level": "1",
    "quality": "0",
    "count": "1",
    "enabled": "true",
    "enableGlobal1": "true",
    "enableGlobal2": "true",
    "statSetIndex": "nil",
    "statSetIndexCalcs": "nil",
}


def _make_gem_element(name: str, templates: dict[str, dict]) -> ET.Element:
    """Build a <Gem .../> element for the given support name."""
    tmpl = templates.get(name.lower())
    attrs = dict(_MINIMAL_GEM_ATTRS)
    if tmpl:
        # Lift the metadata-bearing attrs from the template
        for k in ("gemId", "skillId", "variantId"):
            if tmpl.get(k):
                attrs[k] = tmpl[k]
    attrs["nameSpec"] = name
    el = ET.Element("Gem", attrs)
    return el


def _rewrite_skill_block(
    xml_bytes: bytes,
    main_skill: str,
    target_supports: list[str],
    templates: dict[str, dict],
) -> tuple[bytes, bool]:
    """Find the <Skill> block whose first gem is `main_skill` and replace its
    supports with `target_supports`. Returns (new_xml_bytes, did_rewrite)."""
    if not target_supports:
        return xml_bytes, False
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return xml_bytes, False

    target_skill_block: ET.Element | None = None
    for sk in root.iter("Skill"):
        gems = sk.findall("Gem")
        if not gems:
            continue
        first_name = (gems[0].attrib.get("nameSpec") or "").strip().lower()
        if first_name == main_skill.lower():
            target_skill_block = sk
            break

    if target_skill_block is None:
        return xml_bytes, False

    # Keep the first <Gem> (the main skill) and drop the rest.
    gems = list(target_skill_block.findall("Gem"))
    main_gem = gems[0]
    for g in gems[1:]:
        target_skill_block.remove(g)

    # Insert new supports after the main gem
    insert_at = list(target_skill_block).index(main_gem) + 1
    for name in target_supports:
        new_el = _make_gem_element(name, templates)
        target_skill_block.insert(insert_at, new_el)
        insert_at += 1

    # Mark the block as the active calc target so PoB opens to it
    target_skill_block.set("enabled", "true")
    target_skill_block.set("mainActiveSkill", "1")

    return ET.tostring(root, encoding="utf-8"), True


# ── Public API ─────────────────────────────────────────────────────────────

def build_canonical_pob_code(
    skill: str,
    ascendancy: str,
    recommended_nodes: list[int],
    recommended_supports: Iterable[str] | None = None,
    league: str = "sc",
) -> tuple[str | None, PobProvenance | None]:
    """Return (pob_code, provenance) for the guide.

    pob_code is the surgically-edited canonical export string ready to paste
    into PoB Community 2. provenance is metadata about which scraped build it
    was derived from. Both None if no scraped data exists for this combo.
    """
    path = _jsonl_path(skill, ascendancy, league)
    if not os.path.exists(path) and league != "sc":
        path = _jsonl_path(skill, ascendancy, "sc")
    if not os.path.exists(path):
        return None, None

    target_nodes = set(recommended_nodes or [])
    target_supports = {s for s in (recommended_supports or []) if s}

    chosen_code, provenance = _pick_best_pob(path, target_nodes, target_supports, skill)
    if not chosen_code:
        return None, None

    if not target_supports:
        # Nothing to rewrite — return the picked code as-is
        return chosen_code, provenance

    raw = _decode(chosen_code)
    if raw is None:
        return chosen_code, provenance

    templates = _build_gem_template_index(path)
    new_xml, rewrote = _rewrite_skill_block(
        raw,
        main_skill=skill,
        target_supports=list(target_supports),
        templates=templates,
    )
    if not rewrote:
        # Couldn't find the main-skill block — return the original
        return chosen_code, provenance

    provenance.supports_rewritten = True
    return _encode(new_xml), provenance


# ── Back-compat shim ───────────────────────────────────────────────────────

def get_representative_pob_code(
    skill: str,
    ascendancy: str,
    recommended_nodes: list[int],
    league: str = "sc",
) -> str | None:
    """Legacy entrypoint — picks a code without skill-block surgery.

    Retained for any caller that doesn't yet pass the recommended supports.
    New callers should use `build_canonical_pob_code`.
    """
    code, _ = build_canonical_pob_code(
        skill=skill,
        ascendancy=ascendancy,
        recommended_nodes=recommended_nodes,
        recommended_supports=None,
        league=league,
    )
    return code
