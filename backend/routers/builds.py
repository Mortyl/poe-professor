from fastapi import APIRouter, HTTPException
from models.schemas import BuildRequest, BuildGuide
from services.build_service import generate_build

router = APIRouter()

SKILLS = [
    "Fireball", "Ice Nova", "Lightning Strike", "Blade Vortex",
    "Earthquake", "Tornado Shot", "Arc", "Freezing Pulse",
    "Cyclone", "Splitting Steel", "Explosive Arrow", "Raise Spectre",
    "Summon Skeletons", "Viper Strike", "Flicker Strike", "Storm Call"
]

ASCENDANCIES = [
    "Deadeye", "Raider", "Pathfinder",
    "Elementalist", "Occultist", "Necromancer",
    "Inquisitor", "Hierophant", "Guardian",
    "Assassin", "Saboteur", "Trickster",
    "Juggernaut", "Berserker", "Chieftain",
    "Slayer", "Gladiator", "Champion",
    "Ascendant"
]


@router.get("/skills")
async def get_skills():
    """Get list of available skills."""
    return {"skills": SKILLS}


@router.get("/ascendancies")
async def get_ascendancies():
    """Get list of available ascendancies."""
    return {"ascendancies": ASCENDANCIES}


@router.post("/generate", response_model=BuildGuide)
async def generate(request: BuildRequest):
    """Generate a build guide for a given skill and ascendancy."""
    try:
        guide = await generate_build(request)
        return guide
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
