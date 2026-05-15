import os
from dotenv import load_dotenv
load_dotenv()
from models.schemas import BuildGuide
from services.knowledge_service import build_knowledge_context

USE_MOCK = False


async def generate_build(skill: str, ascendancy: str, weapon_type: str = None, class_name: str = None) -> BuildGuide:
    if USE_MOCK:
        return _get_mock_build(skill, ascendancy, weapon_type, class_name)
    else:
        return await _get_claude_build(skill, ascendancy, weapon_type, class_name)


def _get_mock_build(skill: str, ascendancy: str, weapon_type: str, class_name: str) -> BuildGuide:
    return BuildGuide(
        skill=skill,
        ascendancy=ascendancy,
        overview=f"This is a mock {skill} build for the {ascendancy} ascendancy.",
        passive_tree_notes=f"Focus on nodes that enhance {skill} damage.",
        key_skills=[skill, "Determination", "Grace", "Flame Dash", "Blood Rage"],
        gem_links=[
            f"{skill} - Multistrike - Brutality - Melee Physical Damage",
            "Aura Setup: Determination - Grace",
            "Mobility: Flame Dash - Second Wind",
            "Curse: Vulnerability - Hextouch"
        ],
        gear_priorities=[
            "Helmet: Life, Resistances",
            "Chest: High life, resistances",
            "Gloves: Life, Attack Speed, Resistances",
            "Boots: Life, Movement Speed, Resistances",
            "Weapon: High Physical DPS, Attack Speed",
            "Rings/Amulet: Life, Resistances, Attributes"
        ],
        playstyle_tips="Mock build — connect the Claude API for real AI-generated build guides.",
        disclaimer="⚠️ This is mock data for development."
    )


async def _get_claude_build(skill: str, ascendancy: str, weapon_type: str, class_name: str) -> BuildGuide:
    import anthropic
    import json
    import re

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    knowledge_context = build_knowledge_context(
        class_name=class_name,
        ascendancy=ascendancy,
        weapon_type=weapon_type,
        skill=skill,
    )

    system_prompt = """You are PoEProfessor, an expert Path of Exile 2 build guide creator.

CRITICAL RULES:
- You ONLY reference Path of Exile 2 mechanics, skills, and systems. Never use Path of Exile 1 content.
- If you are unsure whether something exists in PoE2, say so rather than guessing.
- PoE2 has no sockets on gear — skills and support gems are linked directly in the skill menu.
- Support gems in PoE2 are socketed into skill gems directly, not into gear.
- PoE2 has a completely new passive skill tree — do not invent specific node names.
- The PoE2 passive tree has very few Maximum Life nodes compared to PoE1. Do NOT advise stacking life nodes or targeting "150% increased Life from the tree" — that is PoE1 advice. In PoE2, Life comes primarily from gear and Strength, not the passive tree. Passive tree priorities are damage scaling, key notables, and defensive keystones — not life clusters.
- Resistances cap at 75% by default.
- PoE2 has a separate Spirit resource used for auras and persistent skills.
- PoE2 only uses one health flask, one mana flask, and up to 3 charms.
- In PoE2, skill gems are tied to specific weapon types. A skill that requires a mace cannot be used with a bow, staff, or any other weapon type. Never suggest skills that do not match the equipped weapon type. Always respect weapon-skill restrictions.

TONE: Beginner-friendly, practical and honest about uncertainty.

If verified knowledge is provided below, treat it as your primary reference and prioritise it over your training data."""

    if knowledge_context:
        system_prompt += f"\n\n{knowledge_context}"

    prompt = f"""Generate a beginner-friendly build guide for the following Path of Exile 2 build:

Skill: {skill}
Ascendancy: {ascendancy}
Weapon: {weapon_type}
Class: {class_name}

Return a JSON object with exactly these fields:
- overview: string, 2-3 sentences overview of the build
- passive_tree_notes: string, guidance on passive tree priorities using general directions and stat types
- key_skills: list of 5 strings, each a skill name and one-line description e.g. "Lightning Arrow - main damage skill"
- gem_links: list of 4 strings, each in this exact format: "Skill Name - Support1, Support2, Support3"
- gear_priorities: list of 6 strings, each describing one gear slot
- playstyle_tips: string, 2-3 sentences on how to play the build

Return only valid JSON with no markdown, no code fences, no extra explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}]
    )

    content = message.content[0].text
    content = re.sub(r'```json\s*', '', content)
    content = re.sub(r'```\s*', '', content)
    content = content.strip()

    data = json.loads(content)

    if data.get("gem_links") and isinstance(data["gem_links"][0], dict):
        data["gem_links"] = [
            f"{g['skill']}: {', '.join(g['links'])}"
            for g in data["gem_links"]
        ]

    return BuildGuide(
        skill=skill,
        ascendancy=ascendancy,
        disclaimer="⚠️ This build guide is AI-generated and intended as a rough starting point. Always verify with up-to-date community resources.",
        **data
    )
