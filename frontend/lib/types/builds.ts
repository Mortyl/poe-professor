/**
 * Shared types for the Build Guide API.
 *
 * Mirrors the Pydantic shapes from `backend/models/schemas.py:BuildGuide`
 * and its nested types. Imported anywhere a generated build guide is
 * consumed (the wizard page, BuildGuideTome, BuildGuideEditorial, saved
 * build viewers, etc.) — change here once when the API shape evolves.
 */

export interface GemEntry {
  name: string;
  pct: number;
}

export interface SkillGem {
  name: string;
  pct: number;
  supports: GemEntry[];
}

export interface GemLinkData {
  main_skill: string;
  skill_gems: SkillGem[];
  builds_analysed: number;
}

export interface UniqueItem {
  name: string;
  base: string;
  slot: string;
  pct: number;
}

export interface GearSlot {
  slot: string;
  top_unique: UniqueItem | null;
  top_rare_base: string;
  top_rare_base_pct: number;
  top_mods: string[];
}

export interface GearData {
  builds_analysed: number;
  slots: GearSlot[];
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
