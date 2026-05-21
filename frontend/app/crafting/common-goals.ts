/**
 * Common-goals mapping for the crafting tool's *Beginner* mode.
 *
 * Each entry says: "for this item class, here are a handful of curated
 * crafting goals; each goal is just a bundle of RePoE2 mod-family ids
 * that get sent to the backend matcher as `target_mod_groups`."
 *
 * Keep this list short and human-readable — power users will use the
 * Advanced mod-by-mod picker (Phase C2) when that lands.
 *
 * Item-class keys are matched case-insensitively against the parsed
 * item's `item_class`. PoE2 clipboard puts both plural ("Amulets") and
 * singular ("Amulet") forms in the field depending on the item type, so
 * always lowercase the lookup key when matching.
 */

export interface CommonGoal {
  id: string;
  label: string;
  description: string;
  /** RePoE2 group ids the matcher should treat as targets. */
  families: string[];
}

/** Lowercase item class → list of goals. */
export const COMMON_GOALS_BY_CLASS: Record<string, CommonGoal[]> = {
  amulets: [
    {
      id: "life_res",
      label: "Life + Resistances",
      description: "Solid baseline amulet — flat life prefix plus elemental resistances on the suffixes.",
      families: ["IncreasedLife", "FireResistance", "ColdResistance", "LightningResistance", "AllResistances"],
    },
    {
      id: "spell_dps",
      label: "Spell DPS",
      description: "Damage stacking for caster builds — spell damage prefix + crit suffixes.",
      families: ["SpellDamage", "IncreasedCastSpeed", "CriticalStrikeChance", "CriticalStrikeMultiplier"],
    },
    {
      id: "spirit",
      label: "Spirit Stacker",
      description: "Spirit prefix plus life for builds running expensive persistent skills.",
      families: ["BaseSpirit", "IncreasedLife"],
    },
    {
      id: "attributes",
      label: "Attribute Stacker",
      description: "Stack one or more attributes — handy for skill requirements or attribute-scaling builds.",
      families: ["Strength", "Dexterity", "Intelligence", "AllAttributes"],
    },
    {
      id: "gem_level",
      label: "Skill Gem Level",
      description: "Boost the level of your skill gems for a flat damage uplift.",
      families: [
        "GlobalIncreaseSpellSkillGemLevel",
        "GlobalIncreaseMinionSpellSkillGemLevel",
        "GlobalIncreaseMeleeSkillGemLevel",
        "GlobalIncreaseProjectileSkillGemLevel",
      ],
    },
  ],
  "body armours": [
    {
      id: "life_def",
      label: "Life + Defence",
      description: "Life prefix with bonus armour / evasion / energy shield from the same prefix slot.",
      families: [
        "IncreasedLife",
        "MaximumLifeIncreasePercent",
        "GlobalPhysicalDamageReductionRatingPercent",
        "GlobalEvasionRatingPercent",
        "GlobalEnergyShieldPercent",
      ],
    },
    {
      id: "life_res_body",
      label: "Life + Resistances",
      description: "Classic resistance-capping body armour with a life floor.",
      families: ["IncreasedLife", "FireResistance", "ColdResistance", "LightningResistance", "AllResistances"],
    },
    {
      id: "es_caster",
      label: "ES Caster",
      description: "Energy Shield stacking for caster / hybrid builds.",
      families: ["EnergyShield", "GlobalEnergyShieldPercent", "IncreasedMana", "AllResistances"],
    },
    {
      id: "spirit_body",
      label: "Spirit Stacker",
      description: "Body armour with a Spirit prefix for sustaining auras / persistent skills.",
      families: ["BaseSpirit", "IncreasedLife"],
    },
  ],
};

/** Find the common-goals list for an item class. Returns [] for unknown classes. */
export function goalsForClass(itemClass: string): CommonGoal[] {
  if (!itemClass) return [];
  const key = itemClass.toLowerCase().trim();
  return COMMON_GOALS_BY_CLASS[key] ?? [];
}
