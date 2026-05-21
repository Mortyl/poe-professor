import os
import json
from dotenv import load_dotenv
load_dotenv()
from models.schemas import BuildGuide, BuildRequest
from services.knowledge_service import build_knowledge_context
from services.tree_service import recommend_nodes_branched
from services.pob_service import build_canonical_pob_code

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "pob_codes", "reports")


# Wizard precedence — endgame full-meta > league-starter full-meta > exotic (sub-meta sketch)
REPORT_EXP_PRECEDENCE = ("endgame", "league_starter", "exotic")


def _load_report(skill: str, ascendancy: str, report_type: str) -> dict | None:
    """Load a JSON report if it exists. Returns None gracefully if not found.

    Each experience level is tried in REPORT_EXP_PRECEDENCE order. Within an
    exp level, the filename precedence is most-specific → most-legacy:
      1. {skill}_{ascendancy}_{exp}_{type}.json — current per-combo format
      2. {skill}_{exp}_{type}.json              — legacy skill-only (polluted
         across ascendancies; here for back-compat until all combos re-analysed)
      3. {ascendancy}_{exp}_{type}.json         — ancient ascendancy-only fallback
    """
    skill_slug = skill.lower().replace(" ", "_")
    asc_slug   = ascendancy.lower()

    for exp in REPORT_EXP_PRECEDENCE:
        candidates = [
            os.path.join(REPORT_DIR, f"{skill_slug}_{asc_slug}_{exp}_{report_type}.json"),
            os.path.join(REPORT_DIR, f"{skill_slug}_{exp}_{report_type}.json"),
            os.path.join(REPORT_DIR, f"{asc_slug}_{exp}_{report_type}.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
    return None


def build_real_data_context(skill: str, ascendancy: str) -> str:
    """
    Build a context block from scraped poe.ninja data for injection into the system prompt.
    Returns an empty string if no reports are available yet.
    """
    parts = []
    exp_label = "league starter (days 1–14)"

    gem_data = _load_report(skill, ascendancy, "gem_links")
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

    passive_data = _load_report(skill, ascendancy, "passives")
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

# Simple in-memory cache — avoids re-calling the API for the same build request
# during a dev session. Cache is cleared on server restart.
_build_cache: dict[str, BuildGuide] = {}


async def generate_build(request: BuildRequest) -> BuildGuide:
    if USE_MOCK:
        return _get_mock_build(request.skill, request.ascendancy, request.weapon_type, request.class_name)

    return _get_tree_only_build(request)


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


def _get_tree_only_build(request: BuildRequest) -> BuildGuide:
    """Return a BuildGuide with the passive tree and gem links populated from real data."""
    from models.schemas import GemLinkData, SkillGem, GemEntry, UniqueItem, GearData, GearSlot, JewelBase

    tree_result = recommend_nodes_branched(
        skill=request.skill,
        ascendancy=request.ascendancy,
        class_name=request.class_name,
        league_type=request.league_type,
    )
    nodes     = tree_result["core"] + tree_result.get("connectors", [])
    optional  = tree_result.get("optional", [])
    asc_nodes = tree_result.get("asc_nodes", [])

    # Default attacks — not real skills, excluded from gem link display
    DEFAULT_ATTACKS = {"Bow Shot", "Melee Strike", "Unarmed Strike"}

    # Load real gem data if available (heatmap-based gems report)
    gem_link_data = None
    gem_report = _load_report(request.skill, request.ascendancy, "gems")
    if gem_report and gem_report.get("builds_analysed", 0) >= 10:
        skill_gems = [
            SkillGem(
                name=g["name"],
                pct=g["pct"],
                supports=[GemEntry(name=s["name"], pct=s["pct"]) for s in g.get("supports", [])],
            )
            for g in gem_report.get("skill_gems", [])
            if g["name"] not in DEFAULT_ATTACKS
        ]
        gem_link_data = GemLinkData(
            main_skill=request.skill,
            skill_gems=skill_gems,
            builds_analysed=gem_report["builds_analysed"],
        )

    CHARM_SLOT_NAMES = ["Charm 1", "Charm 2", "Charm 3"]
    CHARM_SLOT_SET   = set(CHARM_SLOT_NAMES)

    def _build_gear_data(section: dict) -> GearData | None:
        if not section:
            return None

        raw_slots: dict = section.get("slots", {})
        gear_slots: list[GearSlot] = []

        # ── Regular gear slots ──────────────────────────────────────────────
        for slot_name, slot_data in raw_slots.items():
            if slot_name in CHARM_SLOT_SET:
                continue
            top_rare_base = ""
            top_rare_base_pct = 0.0
            if slot_data.get("rare_bases"):
                top_rare_base = slot_data["rare_bases"][0]["base"]
                top_rare_base_pct = slot_data["rare_bases"][0]["pct"]
            top_unique = None
            if top_rare_base_pct < 1.0 and slot_data.get("uniques"):
                u = slot_data["uniques"][0]
                top_unique = UniqueItem(name=u["name"], base=u["base"], slot=slot_name, pct=u["pct"])
            mod_cap = 6 if slot_name in ("Weapon 1", "Weapon 2") else 4
            top_mods = [m["mod"] for m in slot_data.get("top_mods", [])[:mod_cap]]
            gear_slots.append(GearSlot(
                slot=slot_name,
                top_unique=top_unique,
                top_rare_base=top_rare_base,
                top_rare_base_pct=top_rare_base_pct,
                top_mods=top_mods,
            ))

        # ── Charm slots — promote uniques that beat their magic base ─────────
        charm_bases = section.get("charm_bases", [])

        charm_uniques_map: dict[str, UniqueItem] = {
            u["name"]: UniqueItem(name=u["name"], base=u["base"], slot="Charm", pct=u["pct"])
            for u in section.get("charm_uniques", [])
        }

        # Seed slots with top 3 magic bases
        slots: list[dict] = [
            {"kind": "magic", "base": cb["base"], "name": cb["base"], "pct": cb["pct"], "item": None}
            for cb in charm_bases[:3]
        ]

        slotted_unique_names: set[str] = set()

        for u in sorted(charm_uniques_map.values(), key=lambda x: x.pct, reverse=True):
            entry = {"kind": "unique", "base": u.base, "name": u.name, "pct": u.pct, "item": u}

            # Find a magic slot with the same base type
            same_base_idx = next(
                (i for i, s in enumerate(slots) if s["kind"] == "magic" and s["base"] == u.base),
                None,
            )

            if same_base_idx is not None:
                # Same-base replacement: promote unique in-place if it matches or beats the magic base
                if u.pct >= slots[same_base_idx]["pct"]:
                    slots[same_base_idx] = entry
                    slotted_unique_names.add(u.name)
            else:
                # Different base: insert if it beats the lowest-ranked current slot (or slots < 3)
                if len(slots) < 3 or u.pct >= slots[-1]["pct"]:
                    slots.append(entry)
                    slots.sort(key=lambda x: x["pct"], reverse=True)
                    slots = slots[:3]
                    slotted_unique_names.add(u.name)

        # Assign slots to charm display positions
        for i, slot_name in enumerate(CHARM_SLOT_NAMES):
            if i < len(slots):
                c = slots[i]
                if c["kind"] == "unique":
                    gear_slots.append(GearSlot(
                        slot=slot_name,
                        top_unique=c["item"],
                        top_rare_base="",
                        top_rare_base_pct=0.0,
                        top_mods=[],
                    ))
                else:
                    gear_slots.append(GearSlot(
                        slot=slot_name,
                        top_unique=None,
                        top_rare_base=c["name"],
                        top_rare_base_pct=c["pct"],
                        top_mods=[],
                    ))
            else:
                gear_slots.append(GearSlot(slot=slot_name))

        # Optional unique charms: those that didn't make it into the slots
        top_charm_uniques = sorted(
            [u for u in charm_uniques_map.values()
             if u.name not in slotted_unique_names and u.pct >= 5.0],
            key=lambda x: x.pct, reverse=True,
        )[:4]

        # ── Jewels (10% threshold, top 3 bases) ─────────────────────────────
        top_jewel_bases = [
            JewelBase(base=j["base"], pct=j["pct"], top_mods=j.get("top_mods", []))
            for j in section.get("jewel_bases", [])
            if j["pct"] >= 10.0
        ][:3]
        top_jewel_uniques = [
            UniqueItem(name=j["name"], base=j["base"], slot="Jewel", pct=j["pct"])
            for j in section.get("jewel_uniques", [])
            if j["pct"] >= 10.0
        ][:4]

        return GearData(
            builds_analysed=section.get("builds_analysed", 0),
            slots=gear_slots,
            top_charm_uniques=top_charm_uniques,
            top_jewel_bases=top_jewel_bases,
            top_jewel_uniques=top_jewel_uniques,
        )

    # Load gear report (life/ES split)
    useful_uniques    = []
    useful_uniques_es = []
    gear_data_life    = None
    gear_data_es      = None
    gear_report = _load_report(request.skill, request.ascendancy, "gear")
    if gear_report:
        life_section = gear_report.get("life", {})
        es_section   = gear_report.get("es", {})

        # Build gear data first so we know which uniques are already shown in slots
        gear_data_life = _build_gear_data(life_section)
        gear_data_es   = _build_gear_data(es_section) if es_section.get("builds_analysed", 0) >= 10 else None

        # Collect unique names already displayed in gear slots for each variant
        slotted_life = {
            slot.top_unique.name
            for slot in (gear_data_life.slots if gear_data_life else [])
            if slot.top_unique
        }
        slotted_es = {
            slot.top_unique.name
            for slot in (gear_data_es.slots if gear_data_es else [])
            if slot.top_unique
        }

        # Uniques skewed by top-player bias — too expensive to be realistic league starter advice
        EXCLUDED_UNIQUES = {"Headhunter"}

        # Exclude charms (handled separately), anything already in a gear slot, and chase uniques
        useful_uniques = [
            UniqueItem(name=u["name"], base=u["base"], slot=u["slot"], pct=u["pct"])
            for u in life_section.get("top_uniques", [])
            if "charm" not in u.get("slot", "").lower()
            and u["name"] not in slotted_life
            and u["name"] not in EXCLUDED_UNIQUES
        ][:4]
        useful_uniques_es = [
            UniqueItem(name=u["name"], base=u["base"], slot=u["slot"], pct=u["pct"])
            for u in es_section.get("top_uniques", [])
            if "charm" not in u.get("slot", "").lower()
            and u["name"] not in slotted_es
        ][:4]

    # ── Canonical PoB export ───────────────────────────────────────────
    # Lift the supports we want the emitted PoB to carry from the gems
    # report: pick the skill_gem matching the requested main skill, take
    # its top 5 supports with pct >= 30 (broadly agreed-upon picks).
    canonical_supports: list[str] = []
    if gem_link_data is not None:
        match = next(
            (sg for sg in gem_link_data.skill_gems if sg.name.lower() == request.skill.lower()),
            None,
        )
        # Fall back to first listed if the named skill isn't in the report
        match = match or (gem_link_data.skill_gems[0] if gem_link_data.skill_gems else None)
        if match is not None:
            canonical_supports = [
                s.name for s in sorted(match.supports, key=lambda x: -x.pct)
                if s.pct >= 30.0
            ][:5]

    pob_export, pob_provenance = build_canonical_pob_code(
        skill=request.skill,
        ascendancy=request.ascendancy,
        recommended_nodes=nodes,
        recommended_supports=canonical_supports,
        league=request.league_type,
    )
    pob_provenance_dict = (
        {
            "snapshot": pob_provenance.snapshot,
            "level": pob_provenance.level,
            "node_overlap": pob_provenance.node_overlap,
            "support_overlap": pob_provenance.support_overlap,
            "supports_rewritten": pob_provenance.supports_rewritten,
        }
        if pob_provenance is not None else None
    )

    # data_pending: we have the build in the DB (tree was computed) but no
    # gem/gear/passive report exists yet. Frontend renders a friendly banner
    # explaining the deep scrape hasn't reached this combo yet.
    data_pending = (
        gem_link_data is None
        and gear_data_life is None
        and gear_data_es is None
    )

    return BuildGuide(
        skill=request.skill,
        ascendancy=request.ascendancy,
        overview=f"{request.skill} {request.ascendancy} build.",
        passive_tree_notes="Passive tree generated from real poe.ninja data.",
        key_skills=[request.skill],
        gem_links=[],
        gear_priorities=[],
        playstyle_tips="",
        disclaimer="",
        recommended_nodes=nodes,
        optional_nodes=optional,
        asc_nodes=asc_nodes,
        gem_link_data=gem_link_data,
        useful_uniques=useful_uniques,
        useful_uniques_es=useful_uniques_es,
        gear_data_life=gear_data_life,
        gear_data_es=gear_data_es,
        pob_export=pob_export,
        pob_provenance=pob_provenance_dict,
        data_pending=data_pending,
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
    )
    nodes = tree_result["core"] + tree_result.get("connectors", [])
    optional_nodes = []

    league_labels = {
        "sc":    "Softcore",
        "ssf":   "Solo Self-Found",
        "hc":    "Hardcore",
        "hcssf": "Hardcore Solo Self-Found",
    }
    league_label = league_labels.get(request.league_type, "Softcore")
    experience_label = "league starter (limited passive points, prioritise survivability)"

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

    real_data_context = build_real_data_context(skill, ascendancy)
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
        model="claude-haiku-4-5",
        max_tokens=1024,
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
