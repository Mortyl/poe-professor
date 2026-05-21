"""Shared small utilities used by the pipeline scripts AND the FastAPI services.

Keep this file dependency-light — anything heavy belongs in services/.
"""

# Windows-illegal filename characters that quietly break filesystem writes if
# included in a slug. The `:` in PoE2 skill names like "Spectre: Powered Zealot"
# or "Companion: Elephant Tortoise" was the original culprit — on NTFS,
# `filename:streamname` is interpreted as an Alternate Data Stream, so writes
# silently went into a hidden stream of a 0-byte file named just "spectre" or
# "companion", and the scrape looked successful but produced no usable data.
_WINDOWS_ILLEGAL_FILENAME_CHARS = (":", "<", ">", '"', "|", "?", "*", "\\", "/")
# Characters we strip from slugs purely for readability / consistency.
_NOISY_SLUG_CHARS = ("'", ",")


def slug_for_skill(name: str) -> str:
    """Filename-safe slug for a skill name.

    Lowercases, replaces spaces with underscores, strips characters that are
    illegal on Windows (chiefly `:` from PoE2's Spectre: / Companion: skill
    families) and stylistic noise (`'`, `,`).

    For most skills this produces the same result as the original
    `skill.lower().replace(" ", "_")` pattern; only Spectre/Companion-prefixed
    names produce a different output ("spectre_powered_zealot" vs the broken
    "spectre:_powered_zealot").
    """
    s = name.lower().replace(" ", "_")
    for ch in _WINDOWS_ILLEGAL_FILENAME_CHARS:
        s = s.replace(ch, "")
    for ch in _NOISY_SLUG_CHARS:
        s = s.replace(ch, "")
    return s
