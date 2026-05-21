"""Parse a PoB2 export code into structured build data.

A PoB code is base64(url-safe)-encoded zlib-compressed XML. The XML contains
the user's class, ascendancy, allocated passive nodes, skill groups (active +
supports), and equipped items.

This is the single front-door used by the analyser. It wraps + reuses logic
from `analyse_gems.py`, `analyse_gear.py`, and `analyse_builds.py` so we
don't reimplement decoding in three places.
"""

import base64
import sys
import os
import zlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

# Import the existing parsing helpers from the root backend/ scripts.
# We add the parent dir to sys.path so the absolute imports below work
# whether the analyser is run as `uvicorn` (cwd=backend) or as a test.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from analyse_gems import extract_skill_groups as _extract_skill_groups  # noqa: E402
from analyse_gear import parse_items as _parse_items                    # noqa: E402


@dataclass
class ParsedBuild:
    """Normalised view of a PoB code, ready for the analyser."""
    class_name: str = ""
    ascendancy: str = ""          # display name, e.g. "Deadeye"
    level: int = 0
    allocated_nodes: list[int] = field(default_factory=list)
    skill_groups: list[dict] = field(default_factory=list)
    # skill_groups item shape: {"active": "Lightning Arrow", "supports": ["Martial Tempo", ...]}
    items: dict[str, dict] = field(default_factory=dict)
    # items shape: {"Helmet": {"rarity": "RARE", "name": "", "base": "Iron Helmet", "mods": [...]}, ...}

    def candidate_main_skills(self, min_supports: int = 1) -> list[str]:
        """Return active skills that have at least `min_supports` linked supports.

        Used to populate the main-skill picker on the frontend so the user can
        correct an auto-detection mistake.
        """
        out = []
        seen: set[str] = set()
        for g in self.skill_groups:
            name = (g.get("active") or "").strip()
            if not name or name in seen:
                continue
            if len(g.get("supports", [])) >= min_supports:
                out.append(name)
                seen.add(name)
        return out

    def supports_for_skill(self, skill: str) -> list[str]:
        """Return the support gems linked to the given main skill (case-insensitive).

        Aggregates across multiple skill groups in case the user has the same
        skill socketed in two places (uncommon but possible in PoE2).
        """
        skill_lower = skill.lower()
        out: list[str] = []
        for g in self.skill_groups:
            if (g.get("active") or "").lower() == skill_lower:
                out.extend(s for s in g.get("supports", []) if s)
        # Dedupe while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for s in out:
            if s not in seen:
                seen.add(s)
                deduped.append(s)
        return deduped


def decode_pob(code: str) -> bytes | None:
    """Decode a PoB code (base64+zlib) into raw XML bytes. None on failure."""
    if not code:
        return None
    code = code.strip().replace("-", "+").replace("_", "/")
    pad = 4 - len(code) % 4
    if pad != 4:
        code += "=" * pad
    try:
        return zlib.decompress(base64.b64decode(code))
    except Exception:
        return None


def parse_pob_code(code: str) -> ParsedBuild | None:
    """Decode + parse a PoB code into a ParsedBuild. None on failure."""
    xml_bytes = decode_pob(code)
    if xml_bytes is None:
        return None
    return parse_pob_xml(xml_bytes)


def parse_pob_xml(xml_bytes: bytes) -> ParsedBuild | None:
    """Parse pre-decoded PoB XML into a ParsedBuild. None on parse failure."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    build_el = root.find("Build")
    spec_el = root.find(".//Spec")

    class_name = (build_el.attrib.get("className", "") if build_el is not None else "").strip()
    ascendancy = (build_el.attrib.get("ascendClassName", "") if build_el is not None else "").strip()
    try:
        level = int(build_el.attrib.get("level", 0)) if build_el is not None else 0
    except (TypeError, ValueError):
        level = 0

    allocated: list[int] = []
    if spec_el is not None:
        nodes_str = spec_el.attrib.get("nodes", "")
        allocated = [int(n) for n in nodes_str.split(",") if n.strip().isdigit()]

    skill_groups = _extract_skill_groups(xml_bytes) or []
    items = _parse_items(xml_bytes) or {}

    return ParsedBuild(
        class_name=class_name,
        ascendancy=ascendancy,
        level=level,
        allocated_nodes=allocated,
        skill_groups=skill_groups,
        items=items,
    )
