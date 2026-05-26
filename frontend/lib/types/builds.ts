/**
 * Shared types for the Build Guide API.
 *
 * Mirrors the Pydantic shapes from `backend/models/schemas.py:BuildGuide`
 * and its nested types. Imported anywhere a generated build guide is
 * consumed (the wizard page, BuildGuideTome, BuildGuideEditorial, saved
 * build viewers, etc.) — change here once when the API shape evolves.
 */

/** Semantic adoption label. Mirrors backend `_tier_label`:
 *   mandatory >=85%  ·  recommended >=50%  ·  common >=25%  ·  niche <25% */
export type Tier = "mandatory" | "recommended" | "common" | "niche";

/** A skill's role in the build — only present on gem reports generated
 *  with the role classifier (post-May 2026). */
export type SkillRole = "main" | "trigger" | "aura" | "utility" | "secondary";

export interface TriggerChain {
  trigger_skill: string;     // e.g. "Cast on Critical"
  trigger_pct: number;
}

export interface GemEntry {
  name: string;
  pct: number;
  tier?: Tier;
}

export interface SkillGem {
  name: string;
  pct: number;
  supports: GemEntry[];
  role?: SkillRole;
  tier?: Tier;
  triggered_by?: TriggerChain[];
}

export interface GemLinkData {
  main_skill: string;
  skill_gems: SkillGem[];
  builds_analysed: number;
  trigger_chains?: TriggerChain[];   // top-level for CoC-style builds where main isn't directly cast
}

export interface UniqueItem {
  name: string;
  base: string;
  slot: string;
  pct: number;
  tier?: Tier;
}

export interface GearSlot {
  slot: string;
  top_unique: UniqueItem | null;
  top_rare_base: string;
  top_rare_base_pct: number;
  top_mods: string[];
}

export interface SignaturePair {
  items: string[];           // 2 names for pairs, 3 for trinity
  joint_pct: number;
}

export interface SignatureItems {
  mandatory: UniqueItem[];   // individual uniques >=85%
  pairs:     SignaturePair[];
  trinity:   SignaturePair[];
}

export interface GearData {
  builds_analysed: number;
  slots: GearSlot[];
  top_charm_uniques?: UniqueItem[];
  top_jewel_bases?:   { base: string; pct: number; top_mods: string[] }[];
  top_jewel_uniques?: UniqueItem[];
  signature_items?: SignatureItems | null;
}

export interface LevelBucketSection {
  level_range:     string;   // "80-95" or "96+"
  builds_analysed: number;
  life?: GearData | null;
  es?:   GearData | null;
}

export interface LevelBuckets {
  early?: LevelBucketSection | null;
  late?:  LevelBucketSection | null;
}

/** Whether the displayed combo's data is its destination or a stepping stone.
 *  - continuous   = both LS and EG data exist; the level-bucket toggle works
 *  - migration    = LS-only build; players transition to target_skill at EG
 *  - niche_endgame = LS-only, no migration target — LS data IS canonical
 *  - endgame_only = EG-only, planned endgame build (not league-startable) */
export type TrajectoryType = "continuous" | "migration" | "niche_endgame" | "endgame_only";

export interface BuildTrajectory {
  type:          TrajectoryType;
  target_skill:  string;      // populated only when type='migration'
  target_pct:    number;
}

export interface PobProvenance {
  snapshot: string;
  level: number;
  node_overlap: number;
  support_overlap: number;
  supports_rewritten: boolean;
}

export interface BuildGuide {
  skill: string;
  ascendancy: string;
  overview: string;
  passive_tree_notes: string;
  key_skills: string[];
  gem_links: string[];
  gear_priorities: string[];
  playstyle_tips: string;
  disclaimer: string;
  recommended_nodes: number[];
  optional_nodes: number[];
  asc_nodes: number[];
  gem_link_data: GemLinkData | null;
  useful_uniques: UniqueItem[];
  useful_uniques_es: UniqueItem[];
  gear_data_life: GearData | null;
  gear_data_es: GearData | null;
  level_buckets?: LevelBuckets | null;     // endgame upgrade ladder (early lvl 80-95 / late lvl 96+)
  trajectory?: BuildTrajectory | null;     // is the displayed data the destination or a stepping stone?
  pob_export: string | null;
  pob_provenance: PobProvenance | null;
  data_pending: boolean;
}

/** Companion view-model used by BuildGuideTome / Editorial for breadcrumb / header copy. */
export interface SelectedMeta {
  skill: string;
  ascendancy: string;
  className: string;
  weapon: string;
  leagueType: "sc" | "ssf" | "hc" | "hcssf";
}
