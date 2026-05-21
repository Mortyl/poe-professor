"""Build Analyser endpoint.

Accepts either a pasted PoB code or a poe.ninja account+character pair,
runs the three-axis analyser, and returns a structured report. The
frontend turns this into traffic-light findings per axis.
"""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from models.schemas import AnalyseRequest, BuildAnalysisOut
from services.analysis_service import analyse_build
from services.character_import_service import (
    CharacterImportError,
    import_from_poe_ninja,
    import_from_pob_code,
)

router = APIRouter()


@router.post("/character", response_model=BuildAnalysisOut)
async def analyse_character(req: AnalyseRequest):
    # ── 1. Source-route the input ─────────────────────────────────────
    try:
        if req.source == "pob":
            if not req.pob_code:
                raise HTTPException(status_code=400, detail="pob_code is required when source='pob'.")
            parsed = import_from_pob_code(req.pob_code)
        elif req.source == "poe_ninja":
            parsed = import_from_poe_ninja(
                account=req.account_name or "",
                character=req.character_name or "",
                league=req.league_type or "sc",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown source '{req.source}' — use 'pob' or 'poe_ninja'.",
            )
    except CharacterImportError as e:
        # User-facing problem (bad code, missing character, etc.) — 400 not 500
        raise HTTPException(status_code=400, detail=str(e))

    # ── 2. Run the analyser ───────────────────────────────────────────
    try:
        result = analyse_build(
            parsed,
            main_skill=req.main_skill,
            experience_level=req.experience_level,
        )
    except Exception as e:
        # Real internal errors only — surface generic 500 with detail
        raise HTTPException(status_code=500, detail=f"Analyser failed: {e}")

    # ── 3. Convert dataclasses → response model ───────────────────────
    return BuildAnalysisOut(**asdict(result))
