import os
from pathlib import Path

KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent / "knowledge"

# These files are loaded for every request regardless of class/weapon/skill.
# They contain fundamental mechanics that apply to all builds.
CORE_MECHANICS: list[tuple[str, str]] = [
    # Offense — loaded for every build
    ("scaling/offense", "damage_scaling"),
    ("scaling/offense", "enemy_mitigation"),
    ("scaling/offense", "buffs_and_debuffs"),
    # Defense — loaded for every build
    ("scaling/defense", "life_and_recovery"),
    ("scaling/defense", "resistances"),
    ("scaling/defense", "ailments"),
    ("scaling/defense", "armour"),
    ("scaling/defense", "evasion"),
    ("scaling/defense", "energy_shield"),
    ("scaling/defense", "block"),
    ("scaling/defense", "dodge"),
    ("scaling/defense", "other_defences"),
]

# Maps keywords found in skill/weapon/ascendancy names to mechanics files.
# Format: keyword (lowercase) → (category, filename)
MECHANICS_KEYWORD_MAP: dict[str, list[tuple[str, str]]] = {
    # Ailments — lightning
    "lightning":    [("ailments", "shock")],
    "arc":          [("ailments", "shock"), ("scaling", "critical_strikes")],
    "storm":        [("ailments", "shock")],
    "spark":        [("ailments", "shock")],
    "ball lightning": [("ailments", "shock")],
    "shock":        [("ailments", "shock")],
    # Ailments — fire
    "fire":         [("ailments", "ignite")],
    "fireball":     [("ailments", "ignite")],
    "flame":        [("ailments", "ignite")],
    "ignite":       [("ailments", "ignite"), ("scaling", "damage_over_time")],
    "burning":      [("ailments", "ignite"), ("scaling", "damage_over_time")],
    "infernal":     [("ailments", "ignite")],
    # Ailments — cold
    "cold":         [("ailments", "freeze")],
    "ice":          [("ailments", "freeze")],
    "frost":        [("ailments", "freeze")],
    "glacial":      [("ailments", "freeze")],
    "freeze":       [("ailments", "freeze")],
    "chill":        [("ailments", "freeze")],
    # Ailments — chaos
    "poison":       [("ailments", "poison"), ("scaling", "damage_over_time")],
    "chaos":        [("ailments", "poison")],
    "toxic":        [("ailments", "poison")],
    # Ailments — physical
    "bleed":        [("ailments", "bleed"), ("scaling", "damage_over_time")],
    "bleeding":     [("ailments", "bleed"), ("scaling", "damage_over_time")],
    # Combat
    "slam":         [("combat", "stun"), ("combat", "armour_break")],
    "mace":         [("combat", "stun"), ("combat", "armour_break")],
    "stun":         [("combat", "stun")],
    "block":        [("combat", "block")],
    "shield":       [("combat", "block")],
    "armour break": [("combat", "armour_break")],
    # Scaling
    "crit":         [("scaling", "critical_strikes")],
    "critical":     [("scaling", "critical_strikes")],
    # Resources
    "mana":         [("resources", "mana")],
    "spirit":       [("resources", "spirit")],
    "aura":         [("resources", "spirit")],
    "rage":         [("resources", "rage")],
}


def _load_file(path: Path) -> str | None:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def get_class_knowledge(class_name: str) -> str | None:
    if not class_name:
        return None
    path = KNOWLEDGE_BASE_PATH / "classes" / f"{class_name.lower()}.md"
    return _load_file(path)


def get_ascendancy_knowledge(ascendancy: str, class_name: str = None) -> str | None:
    if not ascendancy:
        return None
    asc_slug = ascendancy.lower().replace(" ", "_")
    if class_name:
        class_slug = class_name.lower().replace(" ", "_")
        path = KNOWLEDGE_BASE_PATH / "ascendancies" / class_slug / f"{asc_slug}.md"
    else:
        path = KNOWLEDGE_BASE_PATH / "ascendancies" / f"{asc_slug}.md"
    return _load_file(path)


def get_weapon_knowledge(weapon_type: str) -> str | None:
    if not weapon_type:
        return None
    slug = weapon_type.lower().replace(" ", "_")
    path = KNOWLEDGE_BASE_PATH / "weapons" / f"{slug}.md"
    return _load_file(path)


def get_skill_knowledge(skill: str) -> str | None:
    if not skill:
        return None
    from util import slug_for_skill
    slug = slug_for_skill(skill)
    path = KNOWLEDGE_BASE_PATH / "skills" / f"{slug}.md"
    return _load_file(path)


def get_mechanic_knowledge(category: str, topic: str) -> str | None:
    """Load a mechanics file from mechanics/<category>/<topic>.md"""
    if not category or not topic:
        return None
    path = KNOWLEDGE_BASE_PATH / "mechanics" / category / f"{topic}.md"
    return _load_file(path)


def infer_mechanics(skill: str = None, weapon_type: str = None, ascendancy: str = None) -> list[tuple[str, str]]:
    """
    Infers which mechanics files to load based on keywords in the skill,
    weapon type, and ascendancy name. Returns a deduplicated list of
    (category, topic) tuples.
    """
    combined = " ".join(filter(None, [skill, weapon_type, ascendancy])).lower()
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []

    for keyword, entries in MECHANICS_KEYWORD_MAP.items():
        if keyword in combined:
            for entry in entries:
                if entry not in seen:
                    seen.add(entry)
                    result.append(entry)

    return result


def build_knowledge_context(
    class_name: str = None,
    ascendancy: str = None,
    weapon_type: str = None,
    skill: str = None,
) -> str:
    """
    Assembles all relevant knowledge into a single context string for
    injection into Claude prompts. Only includes files that exist on disk.
    """
    sections = []

    class_knowledge = get_class_knowledge(class_name)
    if class_knowledge:
        sections.append(f"## Class Knowledge: {class_name}\n{class_knowledge}")

    ascendancy_knowledge = get_ascendancy_knowledge(ascendancy, class_name=class_name)
    if ascendancy_knowledge:
        sections.append(f"## Ascendancy Knowledge: {ascendancy}\n{ascendancy_knowledge}")

    weapon_knowledge = get_weapon_knowledge(weapon_type)
    if weapon_knowledge:
        sections.append(f"## Weapon Knowledge: {weapon_type}\n{weapon_knowledge}")

    skill_knowledge = get_skill_knowledge(skill)
    if skill_knowledge:
        sections.append(f"## Skill Knowledge: {skill}\n{skill_knowledge}")

    # Always load core mechanics files for every build
    all_mechanics = list(CORE_MECHANICS)

    # Add contextually inferred mechanics (skill/weapon/ascendancy specific)
    inferred = infer_mechanics(skill=skill, weapon_type=weapon_type, ascendancy=ascendancy)
    for entry in inferred:
        if entry not in all_mechanics:
            all_mechanics.append(entry)

    mechanics = all_mechanics
    for category, topic in mechanics:
        mechanic_knowledge = get_mechanic_knowledge(category, topic)
        if mechanic_knowledge:
            sections.append(f"## Mechanic: {topic.replace('_', ' ').title()}\n{mechanic_knowledge}")

    if not sections:
        return ""

    return (
        "# PoEProfessor Knowledge Base\n"
        "The following is verified PoE2 knowledge. Use this as your primary reference "
        "and prioritise it over your training data.\n\n"
        + "\n\n---\n\n".join(sections)
    )
