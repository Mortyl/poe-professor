"""Recipe library + matcher for the crafting tool.

Recipes live as JSON files in `backend/crafting/recipes/*.json`. Each one is
a hand-curated crafting strategy expressed in terms of the user's *target
mod families* (not specific mod ids) — e.g. *"give me +Life and Resistances"*
rather than *"give me Life4 and FireResist3 specifically"*. This keeps the
library small and patch-resilient.

Matcher (`find_recipes`):
  1. Filter recipes by item class / ilvl / rarity (applies_to).
  2. Compute coverage_score against the user's target families.
  3. Reject score < 0.5 (recipe can't realistically hit half the targets).
  4. Rank by (guaranteed × 2 + rollable), then by static cost asc.
  5. Return top N (default 3).

Live currency prices come from `currency_price_service` if available; if
not (current state for PoE2), we fall back to each recipe's static
`estimated_cost_chaos_range`.
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field
from typing import Iterable

from services.currency_price_service import chaos_value
from services.mod_pool_service import known_item_classes

RECIPES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "crafting", "recipes",
)

# Default cap on how many recipes we return per request — the UI shows 1-3
# cards so anything past that wastes payload.
DEFAULT_TOP_N = 3
# Minimum coverage to consider a recipe applicable. Below this we'd be lying
# about what the recipe can deliver.
MIN_COVERAGE = 0.5


@dataclass
class RecipeStep:
    """One step the user takes in the workshop."""
    verb: str                  # "Use Essence of Greed"
    currency: str | None = None
    qty: float = 1             # average per attempt (can be fractional)
    outcome: str = ""          # plain-text outcome / branching hint


@dataclass
class Recipe:
    """A crafting strategy from disk, post-load."""
    id: str
    name: str
    description: str
    applies_to: dict           # {item_classes, min_ilvl, starting_rarity}
    guaranteed_mod_families: list[str] = field(default_factory=list)
    rollable_mod_families: list[str] = field(default_factory=list)
    steps: list[RecipeStep] = field(default_factory=list)
    estimated_cost_chaos_range: tuple[float, float] = (0.0, 0.0)
    estimated_success_pct: float | None = None
    notes_for_user: str = ""
    skill_floor: str = "beginner"  # "beginner" | "intermediate" | "advanced"
    # Source filename (for diagnostics)
    _source: str = ""


@dataclass
class MatchResult:
    """One recipe ranked against the user's input."""
    recipe: Recipe
    coverage_score: float           # 0..1 — fraction of user's targets the recipe touches
    guaranteed_coverage: int        # count of user's targets covered by guaranteed_mod_families
    rollable_coverage: int          # count covered by rollable_mod_families (excluding guaranteed)
    live_cost_chaos: float | None   # None when no live price for any step currency
    rank_score: float               # the value used for sorting (higher = better)


# ── Loading ────────────────────────────────────────────────────────────────

_recipes_cache: list[Recipe] | None = None


def _step_from_dict(d: dict) -> RecipeStep:
    return RecipeStep(
        verb=d.get("verb", ""),
        currency=d.get("currency"),
        qty=float(d.get("qty", 1)),
        outcome=d.get("outcome", ""),
    )


def _recipe_from_dict(d: dict, source: str) -> Recipe:
    cost_range = d.get("estimated_cost_chaos_range", [0, 0])
    return Recipe(
        id=d["id"],
        name=d.get("name", d["id"]),
        description=d.get("description", ""),
        applies_to=d.get("applies_to", {}),
        guaranteed_mod_families=list(d.get("guaranteed_mod_families", [])),
        rollable_mod_families=list(d.get("rollable_mod_families", [])),
        steps=[_step_from_dict(s) for s in d.get("steps", [])],
        estimated_cost_chaos_range=(float(cost_range[0]), float(cost_range[1])),
        estimated_success_pct=(
            float(d["estimated_success_pct"]) if "estimated_success_pct" in d else None
        ),
        notes_for_user=d.get("notes_for_user", ""),
        skill_floor=d.get("skill_floor", "beginner"),
        _source=source,
    )


def load_all_recipes() -> list[Recipe]:
    """Read every JSON file in recipes/ once, cache for the lifetime of the
    process. Reload by clearing `_recipes_cache` (e.g. in dev tooling)."""
    global _recipes_cache
    if _recipes_cache is not None:
        return _recipes_cache

    recipes: list[Recipe] = []
    if not os.path.isdir(RECIPES_DIR):
        _recipes_cache = []
        return _recipes_cache

    for path in sorted(glob.glob(os.path.join(RECIPES_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # One bad recipe file shouldn't take the whole library down.
            # Log and skip — a future admin endpoint can surface these.
            print(f"[recipe_service] failed to load {path}: {e}")
            continue
        try:
            recipes.append(_recipe_from_dict(data, source=os.path.basename(path)))
        except KeyError as e:
            print(f"[recipe_service] {path} missing required field {e}")

    _recipes_cache = recipes
    return _recipes_cache


# ── Matcher ────────────────────────────────────────────────────────────────

def _normalize_class(item_class: str) -> str:
    """Accept either 'Amulet' or 'Amulets' (RePoE2 keys are plural, parser
    output can be either). Compare case-insensitively."""
    return item_class.lower().strip().rstrip("s")


def _class_matches(recipe_class: str, item_class: str) -> bool:
    return _normalize_class(recipe_class) == _normalize_class(item_class)


def _rarity_matches(allowed: Iterable[str], rarity: str) -> bool:
    if not allowed:
        return True
    rarity_lower = rarity.lower()
    return any(a.lower() == rarity_lower for a in allowed)


def _applies(recipe: Recipe, item_class: str, ilvl: int, rarity: str) -> bool:
    """Does this recipe accept the given item context?"""
    rules = recipe.applies_to
    classes = rules.get("item_classes", [])
    if classes and not any(_class_matches(c, item_class) for c in classes):
        return False
    if ilvl < int(rules.get("min_ilvl", 0) or 0):
        return False
    allowed_rarities = rules.get("starting_rarity")
    if allowed_rarities and not _rarity_matches(allowed_rarities, rarity):
        return False
    return True


def _coverage_breakdown(
    recipe: Recipe, target_families: set[str],
) -> tuple[int, int]:
    """Returns (guaranteed_hits, rollable_hits). `rollable_hits` excludes
    families also in `guaranteed_mod_families` to avoid double-counting."""
    guaranteed = set(recipe.guaranteed_mod_families)
    rollable_only = set(recipe.rollable_mod_families) - guaranteed
    g_hits = len(target_families & guaranteed)
    r_hits = len(target_families & rollable_only)
    return g_hits, r_hits


def _estimate_live_cost(recipe: Recipe) -> float | None:
    """Sum chaos values across the recipe's steps using live currency prices.
    Returns None if we couldn't price every currency in the recipe — caller
    falls back to the static range."""
    total = 0.0
    for step in recipe.steps:
        if not step.currency:
            continue
        cv = chaos_value(step.currency)
        if cv is None:
            return None
        total += cv * step.qty
    return total


def find_recipes(
    item_class: str,
    ilvl: int,
    rarity: str,
    target_families: Iterable[str],
    top_n: int = DEFAULT_TOP_N,
) -> list[MatchResult]:
    """Return the top recipes for this (item, target) combo, ranked.

    target_families is the set of RePoE2 mod-group ids the user wants
    (e.g. {"IncreasedLife", "FireResistance"}). Empty target = return any
    applicable recipe sorted by static cost asc.
    """
    targets = {f for f in target_families if f}
    matches: list[MatchResult] = []

    for recipe in load_all_recipes():
        if not _applies(recipe, item_class, ilvl, rarity):
            continue

        # Coverage check. When no targets supplied, treat every applicable
        # recipe as fully covering (we're in "browse all options" mode).
        if targets:
            g_hits, r_hits = _coverage_breakdown(recipe, targets)
            coverage = (g_hits + r_hits) / len(targets)
            if coverage < MIN_COVERAGE:
                continue
        else:
            g_hits, r_hits = 0, 0
            coverage = 1.0

        live_cost = _estimate_live_cost(recipe)

        # Rank: prefer guaranteed hits 2x weight over rollable, then break ties
        # on cost ascending (cheaper first). Negative cost for descending sort
        # later (we sort by rank_score desc).
        cost_for_rank = (
            live_cost
            if live_cost is not None
            else (recipe.estimated_cost_chaos_range[0] + recipe.estimated_cost_chaos_range[1]) / 2.0
            or 1.0
        )
        # rank_score combines coverage (high weight) and inverse cost.
        # coverage * 1000 dominates; -log(cost) provides a tiebreaker.
        import math
        rank_score = (g_hits * 2 + r_hits) * 100 - math.log(max(cost_for_rank, 1.0))

        matches.append(MatchResult(
            recipe=recipe,
            coverage_score=coverage,
            guaranteed_coverage=g_hits,
            rollable_coverage=r_hits,
            live_cost_chaos=live_cost,
            rank_score=rank_score,
        ))

    matches.sort(key=lambda m: -m.rank_score)
    return matches[:top_n]


# ── Diagnostics ────────────────────────────────────────────────────────────

def status() -> dict:
    """For /health or debug — what recipes did we load?"""
    recipes = load_all_recipes()
    return {
        "recipes_loaded": len(recipes),
        "recipes_dir": os.path.abspath(RECIPES_DIR),
        "known_classes_sample": known_item_classes()[:5],
        "recipe_ids": [r.id for r in recipes],
    }
