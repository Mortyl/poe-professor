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
    pob_export: Optional[str] = None              # canonical PoB2 export string (base64 zlib XML) — guide supports patched into a real player base
    pob_provenance: Optional[dict] = None         # {snapshot, level, node_overlap, support_overlap, supports_rewritten}
    data_pending: bool = False                    # True when no gem/gear/passive report exists yet — backend has tree only


# ── Build Analyser ─────────────────────────────────────────────────────────

class AnalyseRequest(BaseModel):
    source: str                                   # "pob" | "poe_ninja"
    pob_code: Optional[str] = None                # required when source == "pob"
    account_name: Optional[str] = None            # required when source == "poe_ninja"
    character_name: Optional[str] = None          # required when source == "poe_ninja"
    league_type: str = "sc"                       # for poe.ninja snapshot lookup
    main_skill: Optional[str] = None              # override auto-detected skill
    experience_level: str = "league_starter"      # "league_starter" | "endgame"


class GemFindingOut(BaseModel):
    kind: str
    support: str
    meta_pct: float
    severity: str


class GemAnalysisOut(BaseModel):
    main_skill: str
    builds_analysed: int
    confidence: float
    user_supports: List[str] = []
    findings: List[GemFindingOut] = []
    available: bool = True
    message: str = ""


class PassiveFindingOut(BaseModel):
    kind: str
    node_id: int
    node_name: str
    meta_pct: float
    severity: str


class PassiveAnalysisOut(BaseModel):
    builds_analysed: int
    confidence: float
    user_node_count: int = 0
    findings: List[PassiveFindingOut] = []
    available: bool = True
    message: str = ""


class GearFindingOut(BaseModel):
    slot: str
    kind: str
    message: str
    severity: str


class GearAnalysisOut(BaseModel):
    total_uncapped_res: dict = {}
    findings: List[GearFindingOut] = []
    available: bool = True
    message: str = ""


class BuildAnalysisOut(BaseModel):
    skill: str
    ascendancy: str
    class_name: str
    level: int
    experience_level: str
    candidate_skills: List[str] = []
    gem: GemAnalysisOut
    passive: PassiveAnalysisOut
    gear: GearAnalysisOut
