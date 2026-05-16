from pydantic import BaseModel
from typing import Optional, List


class Player(BaseModel):
    rank: int
    character: str
    account: str
    level: int
    class_name: str
    experience: int
    dead: bool


class League(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class LeaderboardResponse(BaseModel):
    league: str
    players: List[Player]


class BuildRequest(BaseModel):
    skill: str
    ascendancy: str
    weapon_type: str
    class_name: str
    league_type: str = "sc"              # "sc", "ssf", "hc", "hcssf"
    experience_level: str = "league_starter"  # "league_starter" or "endgame"


class BuildGuide(BaseModel):
    skill: str
    ascendancy: str
    overview: str
    passive_tree_notes: str
    key_skills: List[str]
    gem_links: List[str]
    gear_priorities: List[str]
    playstyle_tips: str
    disclaimer: str
    recommended_nodes: List[int] = []   # core / mandatory nodes (gold)
    optional_nodes: List[int] = []      # optional nodes (teal)
