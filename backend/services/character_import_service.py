"""Two ways to feed a PoB code into the analyser.

1. `import_from_pob_code(code)` — user pasted their own PoB export string.
2. `import_from_poe_ninja(account, character)` — fetch the PoB code from
   poe.ninja's public character endpoint. Requires the user to have linked
   their pathofexile.com account to poe.ninja (one-time, 90-day window).
   Reuses the helpers from `scrape_poeninja.py` so the auth/rate-limit
   behaviour stays consistent with the rest of the pipeline.

Both adapters return a `ParsedBuild` or raise `CharacterImportError`.
"""

from __future__ import annotations

import os
import sys

from services.pob_parser import ParsedBuild, parse_pob_code

# Make the root backend scripts importable from this service module.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


class CharacterImportError(Exception):
    """Raised when we can't produce a ParsedBuild from the given input."""


def import_from_pob_code(code: str) -> ParsedBuild:
    """Decode a user-pasted PoB code into a ParsedBuild."""
    if not code or not code.strip():
        raise CharacterImportError("Empty PoB code.")
    parsed = parse_pob_code(code)
    if parsed is None:
        raise CharacterImportError(
            "Could not decode that PoB code — paste only the export string, "
            "not the URL or surrounding text."
        )
    if not parsed.ascendancy:
        raise CharacterImportError(
            "PoB code decoded but no ascendancy was found — has this character "
            "ascended yet?"
        )
    return parsed


def import_from_poe_ninja(account: str, character: str, league: str = "sc") -> ParsedBuild:
    """Fetch the latest indexed PoB code for this character via poe.ninja.

    Requires the user to have connected their pathofexile.com account to
    poe.ninja so the character is indexed. We piggy-back on the same
    endpoint our scraper already uses (`/poe2/api/builds/{snap}/character`).
    """
    if not account or not account.strip():
        raise CharacterImportError("Account name is required.")
    if not character or not character.strip():
        raise CharacterImportError("Character name is required.")

    # Import lazily — keeps the FastAPI router from paying urllib/gzip import
    # cost at startup when only the paste path is used.
    try:
        from scrape_poeninja import get_snapshot, fetch_pob_code
    except ImportError as e:
        raise CharacterImportError(
            f"Internal: poe.ninja scraper helpers not importable ({e})."
        )

    try:
        version, snap_name, _labels, _pids = get_snapshot(league)
    except Exception as e:
        raise CharacterImportError(
            f"Could not fetch poe.ninja snapshot info: {e}"
        )

    code = fetch_pob_code(version, snap_name, account.strip(), character.strip(), "")
    if not code:
        raise CharacterImportError(
            f"poe.ninja has no PoB code indexed for '{character}' on account "
            f"'{account}'. Make sure your pathofexile.com account is connected "
            f"to poe.ninja and the character is public. The account name is the "
            f"poe.ninja form (e.g. 'YourName-1234')."
        )

    parsed = parse_pob_code(code)
    if parsed is None:
        raise CharacterImportError(
            "poe.ninja returned a PoB code but it failed to decode. This is "
            "rare and usually means the indexed snapshot is corrupt — try again "
            "later or paste the code manually."
        )
    return parsed
