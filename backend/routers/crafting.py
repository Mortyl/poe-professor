"""Crafting Architect endpoints.

POST /api/crafting/analyse  → parse pasted item + match against recipe library
GET  /api/crafting/status   → diagnostic (recipes loaded, etc.)

Phase B scope: end-to-end paste → recipe ranking. Recipe library is small
(~3 starter recipes); will grow in Phase D.
"""

from fastapi import APIRouter, HTTPException

from models.schemas import (
    CraftAnalyseRequest,
    CraftAnalyseResponse,
    ParsedItemOut,
    RecipeOut,
    RecipeStepOut,
)
from services.item_parser import ItemParseError, parse_item_text
from services.recipe_service import find_recipes, status as recipe_status

router = APIRouter()


@router.post("/analyse", response_model=CraftAnalyseResponse)
async def analyse(req: CraftAnalyseRequest):
    # 1. Parse the pasted clipboard text
    try:
        parsed = parse_item_text(req.item_text)
    except ItemParseError as e:
        raise HTTPException(status_code=400, detail=str(e))

    item_out = ParsedItemOut(
        item_class=parsed.item_class,
        rarity=parsed.rarity,
        name=parsed.name,
        base_type=parsed.base_type,
        item_level=parsed.item_level,
        quality=parsed.quality,
        implicits=parsed.implicits,
        explicit_mods=parsed.explicit_mods,
        corrupted=parsed.corrupted,
        mirrored=parsed.mirrored,
        warnings=parsed.warnings,
    )

    # 2. Match recipes
    matches = find_recipes(
        item_class=parsed.item_class,
        ilvl=parsed.item_level,
        rarity=parsed.rarity,
        target_families=set(req.target_mod_groups or []),
        top_n=max(1, min(req.top_n, 10)),
    )

    # 3. Project to wire shape
    recipes_out = [
        RecipeOut(
            id=m.recipe.id,
            name=m.recipe.name,
            description=m.recipe.description,
            guaranteed_mod_families=m.recipe.guaranteed_mod_families,
            rollable_mod_families=m.recipe.rollable_mod_families,
            steps=[
                RecipeStepOut(
                    verb=s.verb,
                    currency=s.currency,
                    qty=s.qty,
                    outcome=s.outcome,
                )
                for s in m.recipe.steps
            ],
            estimated_cost_chaos_range=list(m.recipe.estimated_cost_chaos_range),
            estimated_success_pct=m.recipe.estimated_success_pct,
            notes_for_user=m.recipe.notes_for_user,
            skill_floor=m.recipe.skill_floor,
            coverage_score=m.coverage_score,
            guaranteed_coverage=m.guaranteed_coverage,
            rollable_coverage=m.rollable_coverage,
            live_cost_chaos=m.live_cost_chaos,
        )
        for m in matches
    ]

    response = CraftAnalyseResponse(item=item_out, recipes=recipes_out)

    if not recipes_out:
        # Give the user a useful reason rather than just an empty list.
        if not parsed.item_class:
            response.no_recipes_reason = (
                "Couldn't identify the item class from the pasted text. "
                "Try copying the item again from in-game."
            )
        elif parsed.item_level == 0:
            response.no_recipes_reason = (
                "No Item Level detected — recipes need ilvl to know what tier "
                "of mods can roll."
            )
        elif not req.target_mod_groups:
            response.no_recipes_reason = (
                f"No applicable recipes for {parsed.item_class} yet. The library "
                "currently covers Amulets and Body Armours; more coming in Phase D."
            )
        else:
            response.no_recipes_reason = (
                f"No recipe in the library covers ≥50% of your chosen target "
                f"mods for a {parsed.rarity.lower()} {parsed.item_class}. Try "
                "fewer / different target mods, or check if the item rarity "
                "matches what the recipes expect (most starter recipes start "
                "from a normal-rarity base)."
            )

    return response


@router.get("/status")
async def status():
    return recipe_status()
