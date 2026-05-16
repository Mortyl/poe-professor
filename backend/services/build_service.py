import os
import json
from dotenv import load_dotenv
load_dotenv()
from models.schemas import BuildGuide, BuildRequest
from services.knowledge_service import build_knowledge_context
from services.tree_service import recommend_nodes_branched

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "pob_codes", "reports")


def _load_report(skill: str, ascendancy: str, experience_level: str, report_type: str) -> dict | None:
    """Load a JSON report if it exists. Returns None gracefully if not found."""
    skill_slug = skill.lower().replace(" ", "_")
    asc_slug   = ascendancy.lower()
    exp        = experience_level

    candidates = [
        # skill-specific report (gem links)
        os.path.join(REPORT_DIR, f"{skill_slug}_{exp}_{report_type}.json"),
        # ascendancy-specific report (passives)
        os.path.join(REPORT_DIR, f"{asc_slug}_{exp}_{report_type}.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return None


def build_real_data_context(skill: str, ascendancy: str, experience_level: str) -> str:
    """
    Build a context block from scraped poe.ninja data for injection into the system prompt.
    Returns an empty string if no reports are available yet.
    """
    parts = []
    exp_label = "league starter (days 1–14)" if experience_level == "league_starter" else "endgame (week 3+)"

    gem_data = _load_report(skill, ascendancy, experience_level, "gem_links")
    if gem_data and gem_data.get("builds_analysed", 0) >= 10:
        n = gem_data["builds_analysed"]
        supports = gem_data.get("top_supports", [])
        link_sets = gem_data.get("top_link_sets", [])

        lines = [f"GEM LINKS for {skill} ({n} real {exp_label} builds on poe.ninja):"]
        for s in supports[:8]:
            lines.append(f"  - {s['name']}: {s['pct']}% of builds")
        if link_sets:
            top = link_sets[0]
            lines.append(f"  Most common link set: {' + '.join(top['gems'])} ({top['pct']}%)")
        lines.append("Use this data for gem_links. Prioritise supports above 30%.")
        parts.append("\n".join(lines))

    passive_data = _load_report(skill, ascendancy, experience_level, "passives")
    if passive_data and passive_data.get("builds_analysed", 0) >= 10:
        n = passive_data["builds_analysed"]
        notables = passive_data.get("top_notables", [])
        asc_nodes = passive_data.get("top_asc_nodes", [])

        lines = [f"PASSIVE TREE for {ascendancy} ({n} real {exp_label} builds on poe.ninja):"]
        if notables:
            lines.append("  Most taken notable nodes:")
            for node in notables[:10]:
                lines.append(f"    - {node['name']}: {node['pct']}%")
        if asc_nodes:
            lines.append("  Ascendancy nodes taken:")
            for node in asc_nodes[:6]:
                lines.append(f"    - {node['name']}: {node['pct']}%")
        lines.append("Use this data to inform passive_tree_notes. Recommend notables above 50%.")
        parts.append("\n".join(lines))

    if not parts:
        return ""

    header = f"\nVERIFIED DATA FROM REAL POE.NINJA BUILDS ({exp_label.upper()}):"
    return header + "\n\n" + "\n\n".join(parts)

USE_MOCK = False


async def generate_build(request: BuildRequest) -> BuildGuide:
    if USE_MOCK:
        return _get_mock_build(request.skill, request.ascendancy, request.weapon_type, request.class_name)
    else:
        return await _get_claude_build(request)


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


async def _get_claude_build(request: BuildRequest) -> BuildGuide:
    import anthropic
    import json
    import re

    skill = request.skill
    ascendancy = request.ascendancy
    weapon_type = request.weapon_type
    class_name = request.class_name

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    knowledge_context = build_knowledge_context(
        class_name=class_name,
        ascendancy=ascendancy,
        weapon_type=weapon_type,
        skill=skill,
    )

    tree_result = recommend_nodes_branched(
        skill=skill,
        ascendancy=ascendancy,
        class_name=class_name,
        league_type=request.league_type,
        experience_level=request.experience_level,
    )
    nodes = tree_result["core"]
    optional_nodes = [n for b in tree_result.get("branches", []) for n in b["nodes"]]

    league_labels = {
        "sc":    "Softcore",
        "ssf":   "Solo Self-Found",
        "hc":    "Hardcore",
        "hcssf": "Hardcore Solo Self-Found",
    }
    league_label = league_labels.get(request.league_type, "Softcore")
    experience_label = "league starter (limited passive points, prioritise survivability)" if request.experience_level == "league_starter" else "endgame (full passive allocation, maximise damage)"

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

    real_data_context = build_real_data_context(skill, ascendancy, request.experience_level)
    if real_data_context:
        system_prompt += f"\n\n{real_data_context}"

    prompt = f"""Generate a beginner-friendly build guide for the following Path of Exile 2 build:

Skill: {skill}
Ascendancy: {ascendancy}
Weapon: {weapon_type}
Class: {class_name}
League: {league_label}
Experience level: {experience_label}

Return a JSON object with exactly these fields:
- overview: string, 2-3 sentences overview of the build
- passive_tree_notes: string, guidance on passive tree priorities using general directions and stat types, tailored to the build focus and experience level above
- key_skills: list of 5 strings, each a skill name and one-line description e.g. "Lightning Arrow - main damage skill"
- gem_links: list of 4 strings, each in this exact format: "Skill Name - Support1, Support2, Support3"
- gear_priorities: list of 6 strings, each describing one gear slot
- playstyle_tips: string, 2-3 sentences on how to play the build

Return only valid JSON with no markdown, no code fences, no extra explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
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
        recommended_nodes=nodes,
        optional_nodes=optional_nodes,
        **data
    )
