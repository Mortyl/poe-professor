"""Tier list endpoint.

GET /tier-list?league=sc&mode=composite

Returns a S/A/B/C/D tier list of meta builds grouped by archetype.
"""

from fastapi import APIRouter, HTTPException, Query

from services.tier_list_service import build_tier_list

router = APIRouter()


@router.get("/tier-list")
async def tier_list(
    league: str = Query(default="sc", pattern="^(sc|hc|ssf|hcssf)$"),
    mode: str = Query(default="composite", pattern="^(composite|league_starter|endgame)$"),
):
    try:
        return build_tier_list(league=league, mode=mode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build tier list: {e}")
