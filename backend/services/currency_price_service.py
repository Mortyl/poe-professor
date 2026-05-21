"""Live currency prices from poe.ninja (with graceful fallback to static).

State of play (May 2026): poe.ninja serves PoE2 currency data on their site
but their public API path for PoE2 currency is undocumented. The PoE1 form
(`/api/data/currencyoverview?league=...&type=Currency`) 404s under `/poe2/`,
and the index-state endpoint only exposes league metadata, not prices.

For v1, the crafting engine sorts recipes by each recipe's hand-curated
`estimated_cost_chaos_range`. This module ATTEMPTS to overlay live prices
when available but is safe to leave returning None forever — callers must
handle None gracefully.

When/if we identify the right endpoint, swap in the URL in `_PRICE_URLS`
and the rest of the system picks up live prices automatically.
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Optional

# Cache TTL — poe.ninja updates prices ~hourly; one hour is fine.
_CACHE_TTL_SECONDS = 3600

# Candidate URLs to try in order. Add new candidates here as we find them.
# Each one is tested at startup; the first that returns valid JSON wins.
_PRICE_URLS = [
    # These are speculative — none confirmed working as of May 2026.
    # Kept for documentation / future probing.
    # "https://poe.ninja/poe2/api/data/currencyoverview?league=vaal&type=Currency",
    # "https://poe.ninja/api/poe2/currencyoverview?league=vaal&type=Currency",
]

# In-memory cache: { currency_name (lowercase) → chaos_value }
_prices: dict[str, float] = {}
_last_fetch_ts: float = 0
_fetch_attempted: bool = False
_fetch_succeeded: bool = False


def _refresh_prices() -> bool:
    """Attempt to refresh prices from one of the candidate URLs.
    Returns True if at least one URL returned usable data."""
    global _prices, _last_fetch_ts, _fetch_attempted, _fetch_succeeded
    _fetch_attempted = True

    for url in _PRICE_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "poeprofessor/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
            continue

        lines = data.get("lines", []) if isinstance(data, dict) else []
        if not lines:
            continue

        fresh: dict[str, float] = {}
        for line in lines:
            name = line.get("currencyTypeName") or line.get("name")
            chaos = line.get("chaosEquivalent")
            if name and isinstance(chaos, (int, float)):
                fresh[name.lower()] = float(chaos)
        if fresh:
            _prices = fresh
            _last_fetch_ts = time.time()
            _fetch_succeeded = True
            return True

    return False


def chaos_value(currency_name: str) -> Optional[float]:
    """Return the chaos value of a currency, or None if we don't have a price.

    Callers MUST handle None — recipes have static fallback ranges. The price
    layer is enhancement, not a hard dependency.
    """
    if not currency_name:
        return None

    # Refresh on TTL expiry. Skip retries during a single TTL window if the
    # first attempt failed — no point hammering an endpoint we know is down.
    now = time.time()
    cache_stale = (now - _last_fetch_ts) > _CACHE_TTL_SECONDS
    if cache_stale and (not _fetch_attempted or _fetch_succeeded):
        _refresh_prices()

    # Chaos Orb is the base unit
    if currency_name.lower() == "chaos orb":
        return 1.0

    return _prices.get(currency_name.lower())


def status() -> dict:
    """Diagnostic snapshot — useful for /health or admin debugging."""
    return {
        "fetch_attempted": _fetch_attempted,
        "fetch_succeeded": _fetch_succeeded,
        "cached_currencies": len(_prices),
        "last_fetch_ts": _last_fetch_ts,
        "candidate_url_count": len(_PRICE_URLS),
    }
