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


class GemEntry(BaseModel):
    name: str
    pct: float


class SkillGem(BaseModel):
    name: str
    pct: float                    # % of builds using this active skill
    supports: List[GemEntry]      # top supports linked to this skill, ordered by adoption %


class GemLinkData(BaseModel):
    main_skill: str               # primary skill (e.g. "Lightning Arrow")
    skill_gems: List[SkillGem]    # active skills with their per-skill supports
    builds_analysed: int = 0


class UniqueItem(BaseModel):
    name: str
    base: str
    slot: str
    pct: float


class GearSlot(BaseModel):
    slot: str
    top_unique: Optional["UniqueItem"] = None  # dominant unique if any
    top_rare_base: str = ""
    top_rare_base_pct: float = 0.0
    top_mods: List[str] = []


class JewelBase(BaseModel):
    base: str
    pct: float
    top_mods: List[str] = []


class GearData(BaseModel):
    builds_analysed: int = 0
    slots: List[GearSlot] = []
    top_charm_uniques: List["UniqueItem"] = []
    top_jewel_bases: List["JewelBase"] = []
    top_jewel_uniques: List["UniqueItem"] = []


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
    asc_nodes: List[int] = []           # ascendancy paid nodes in rank order (top 8)
    gem_link_data: Optional[GemLinkData] = None  # structured gem data from real builds
    useful_uniques: List[UniqueItem] = []         # top unique items (life builds)
    useful_uniques_es: List[UniqueItem] = []      # top unique items (ES builds)
    gear_data_life: Optional[GearData] = None     # per-slot gear — life builds
    gear_data_es: Optional[GearData] = None       # per-slot gear — ES builds
