"""Parse PoE2 in-game clipboard item text into structured data.

When the player presses Ctrl+C on an item, PoE2 puts a text representation
on the clipboard with sections separated by `--------`. This module turns
that text into a `ParsedItem` dataclass the crafting matcher can reason
about (item class, base type, rarity, ilvl, current mods).

The format is the same shape as PoE1's clipboard text, with minor
differences (no socket linking, different attribute requirement format).

Example input:

    Item Class: Amulets
    Rarity: Rare
    Death Knight
    Onyx Amulet
    --------
    Quality: 0
    --------
    Item Level: 80
    --------
    +15 to Strength
    --------
    +62 to maximum Life
    +30% to Lightning Resistance
    --------
    Corrupted

We deliberately keep the parser permissive — PoE adds new line shapes
across patches (sockets / runes / desecrated implicit headers). When a
line doesn't match a recognised pattern we just drop it into the explicit
mods list as opaque text; the recipe matcher doesn't depend on mod
identification for v1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Regexes for the structured lines ───────────────────────────────────────
_RE_ITEM_CLASS = re.compile(r"^Item Class:\s*(.+)$")
_RE_RARITY = re.compile(r"^Rarity:\s*(.+)$")
_RE_ITEM_LEVEL = re.compile(r"^Item Level:\s*(\d+)")
_RE_QUALITY = re.compile(r"^Quality:\s*\+?(\d+)%?")
_RE_SECTION_SEP = re.compile(r"^-{3,}\s*$")

# Sections that aren't mod lines — skip when collecting mods
_NON_MOD_PREFIXES = (
    "Item Level:",
    "Quality:",
    "Quality (",
    "Sockets:",
    "Charm Slots:",
    "Requirements:",
    "Stack Size:",
    "Armour:",
    "Evasion Rating:",
    "Energy Shield:",
    "Block chance:",
    "Spirit:",
    "Physical Damage:",
    "Elemental Damage:",
    "Critical Hit Chance:",
    "Attacks per Second:",
    "Weapon Range:",
    "Map Tier:",
    "Area Level:",
    "Level:",
    "Strength:",
    "Dexterity:",
    "Intelligence:",
    "Note:",
)

# Status lines that don't carry mod info but should be flagged
_STATUS_CORRUPTED = "Corrupted"
_STATUS_MIRRORED = "Mirrored"
_STATUS_UNIDENTIFIED = "Unidentified"

# Mod-section curly-brace headers we should strip but recognise — e.g.
# "{ Prefix Modifier "Pricklish" — Attribute }" — purely informational.
_RE_MOD_HEADER = re.compile(r"^\{[^}]*\}\s*$")


@dataclass
class ParsedItem:
    """Structured projection of a clipboard item, ready for the matcher."""
    raw: str
    item_class: str = ""                 # "Amulet", "Body Armours", etc.
    rarity: str = ""                     # "NORMAL" | "MAGIC" | "RARE" | "UNIQUE"
    name: str = ""                       # Rare/unique only — "Death Knight" / "Astramentis"
    base_type: str = ""                  # "Onyx Amulet", "Plate Vest"
    item_level: int = 0
    quality: int = 0
    implicits: list[str] = field(default_factory=list)
    explicit_mods: list[str] = field(default_factory=list)
    corrupted: bool = False
    mirrored: bool = False
    unidentified: bool = False
    # Diagnostics — fed back to the user when parsing partially fails
    warnings: list[str] = field(default_factory=list)


class ItemParseError(Exception):
    """Raised when the input doesn't look like a PoE clipboard string at all."""


def parse_item_text(text: str) -> ParsedItem:
    """Parse a raw clipboard string into a ParsedItem.

    Always returns a ParsedItem; if the text doesn't look like an item at
    all (e.g. empty / unrelated paste), raises ItemParseError.
    """
    if not text or not text.strip():
        raise ItemParseError("Empty input — paste the full item text from in-game.")

    # PoE clipboard always begins with `Item Class:` since the 2024 update.
    # If we don't see it within the first few lines, the user pasted something
    # else (PoB code, build URL, etc.) — bail with a helpful error.
    head = "\n".join(text.splitlines()[:5])
    if "Item Class:" not in head:
        raise ItemParseError(
            "Doesn't look like a PoE2 item. In-game press Ctrl+C on the item "
            "and paste the full text (it should start with 'Item Class:').",
        )

    item = ParsedItem(raw=text)

    # ── Split into sections delimited by `--------` ──────────────────────
    sections: list[list[str]] = [[]]
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if _RE_SECTION_SEP.match(line):
            sections.append([])
            continue
        if line:
            sections[-1].append(line)

    # ── Section 0 — header (class, rarity, name, base) ──────────────────
    head_section = sections[0] if sections else []
    name_buffer: list[str] = []
    for line in head_section:
        m = _RE_ITEM_CLASS.match(line)
        if m:
            item.item_class = m.group(1).strip()
            continue
        m = _RE_RARITY.match(line)
        if m:
            item.rarity = m.group(1).strip().upper()
            continue
        # Anything else in the header section is name / base
        name_buffer.append(line)

    # Rare and unique items: first non-meta line is the name, second is the base.
    # Normal / magic items: the line is the base (with optional magic prefix/suffix).
    if item.rarity in ("RARE", "UNIQUE") and len(name_buffer) >= 2:
        item.name = name_buffer[0]
        item.base_type = name_buffer[1]
    elif name_buffer:
        # Normal/magic — name_buffer holds the base type (possibly with magic affixes
        # joined in; e.g. "Sturdy Plate Vest of Strength"). We keep it whole — the
        # matcher works off item_class, ilvl and rarity, not the magic affix wording.
        item.base_type = name_buffer[-1]

    # ── Subsequent sections — ilvl, quality, mods, status ───────────────
    # We walk each section and try to classify it. Mod sections are the
    # ones whose lines look like neither header lines nor key:value lines.
    for sec in sections[1:]:
        if not sec:
            continue

        # Single-line status flags (Corrupted / Mirrored / Unidentified)
        if len(sec) == 1:
            single = sec[0]
            if single == _STATUS_CORRUPTED:
                item.corrupted = True
                continue
            if single == _STATUS_MIRRORED:
                item.mirrored = True
                continue
            if single == _STATUS_UNIDENTIFIED:
                item.unidentified = True
                continue

        # Try the structured fields first
        consumed = False
        for line in sec:
            m = _RE_ITEM_LEVEL.match(line)
            if m:
                item.item_level = int(m.group(1))
                consumed = True
            m = _RE_QUALITY.match(line)
            if m:
                item.quality = int(m.group(1))
                consumed = True
        if consumed and not any(_is_mod_line(l) for l in sec):
            continue

        # Otherwise treat as a mod section. Implicit mods often appear in a
        # section labelled (implicit) inline; PoE2 clipboard puts a curly-brace
        # `{ Implicit Modifier ... }` header line before each one. Detect that.
        implicit_flag = any("Implicit" in line for line in sec if line.startswith("{"))
        for line in sec:
            if _RE_MOD_HEADER.match(line):
                continue   # curly-brace metadata header, skip
            if any(line.startswith(p) for p in _NON_MOD_PREFIXES):
                continue   # base stats, requirements, etc.
            if _is_mod_line(line):
                if implicit_flag:
                    item.implicits.append(line)
                else:
                    item.explicit_mods.append(line)

    if not item.item_class:
        item.warnings.append("Could not detect Item Class — recipe matching may misfire.")
    if not item.rarity:
        item.warnings.append("Could not detect Rarity — falling back to 'normal'.")
        item.rarity = "NORMAL"
    if item.item_level == 0:
        item.warnings.append("Could not detect Item Level — assuming 1 (will limit recipe options).")

    return item


# ── Helpers ────────────────────────────────────────────────────────────────

def _is_mod_line(line: str) -> bool:
    """A 'mod line' is any non-structural line that isn't an obvious status flag
    or a key:value metadata line. PoE mod text contains numbers, +, %, etc.
    Reasonable heuristic: not a pure word, has either a digit or starts with +."""
    if not line:
        return False
    if line in (_STATUS_CORRUPTED, _STATUS_MIRRORED, _STATUS_UNIDENTIFIED):
        return False
    if any(line.startswith(p) for p in _NON_MOD_PREFIXES):
        return False
    if _RE_MOD_HEADER.match(line):
        return False
    return bool(re.search(r"[\d+%]", line))
