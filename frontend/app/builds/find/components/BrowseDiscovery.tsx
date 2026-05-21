"use client";

import { useState } from "react";
import styles from "./discovery.module.css";

interface Props {
  onSelectBuild: (skill: string, ascendancy: string) => void;
  middle?: React.ReactNode;
}

// ── Featured editorial lists ─────────────────────────────────────────────────
// TODO: load from JSON files under backend/knowledge/featured/ once
// they're authored. Each list is hand-curated by Marcus per league.
interface FeaturedList {
  tag: string;
  title: string;
  blurb: string;
  count: number;
}

const FEATURED: FeaturedList[] = [
  {
    tag: "League Starter",
    title: "Best 3 builds to start Fate of the Vaal",
    blurb: "Hand-picked combos that level smoothly, hit endgame on a low budget, and scale into mapping. Updated for this league's mechanics.",
    count: 3,
  },
  {
    tag: "Endgame",
    title: "Builds that can do all content",
    blurb: "Versatile setups that comfortably handle mapping, bossing, delve, and T17s. No single-purpose specialists.",
    count: 5,
  },
  {
    tag: "Defensive",
    title: "Tankiest builds for HC players",
    blurb: "Highest survivability against one-shots. Layered defenses, capped resists, big EHP pools.",
    count: 4,
  },
];

// ── Facet filter options ─────────────────────────────────────────────────────
const FACETS = {
  damage:   { label: "Damage",    options: ["Any", "Lightning", "Cold", "Fire", "Chaos", "Physical"] },
  defense:  { label: "Defense",   options: ["Any", "Life", "Energy Shield", "Hybrid", "CI"] },
  content:  { label: "Content",   options: ["Any", "Mapping", "Bossing", "All content", "Delve / Mechanic"] },
  budget:   { label: "Budget",    options: ["Any", "SSF / no budget", "Low (under 5 div)", "Mid (5–50 div)", "Mirror tier"] },
  playstyle:{ label: "Playstyle", options: ["Any", "Speed mapping", "Tanky / methodical", "Glass cannon", "One-button"] },
  phase:    { label: "Phase",     options: ["All", "League starter only", "Endgame only", "Exotic / niche"] },
} as const;

type FacetKey = keyof typeof FACETS;

// ── Sample faceted-results data ──────────────────────────────────────────────
// TODO: replace with a real /api/builds/browse?flat=true call that returns
// a flat build list with auto-derived tags (damage type, weapon, defense)
// plus Marcus-curated tags (content focus, budget, playstyle).
interface SampleBuild {
  skill: string;
  ascendancy: string;
  tags: string[];
  n: number;
  exotic?: boolean;
}

const SAMPLE_BUILDS: SampleBuild[] = [
  { skill: "Lightning Arrow", ascendancy: "Deadeye",     tags: ["Bow", "Lightning", "All content"], n: 378 },
  { skill: "Toxic Growth",    ascendancy: "Pathfinder",  tags: ["Chaos", "DoT", "Low budget"],      n: 294 },
  { skill: "Spark",           ascendancy: "Stormweaver", tags: ["Lightning", "Spell", "Speed"],     n: 281 },
  { skill: "Pounce",          ascendancy: "Witchhunter", tags: ["Physical"],                        n: 120, exotic: true },
];

// ── Component ────────────────────────────────────────────────────────────────
export default function BrowseDiscovery({ onSelectBuild, middle }: Props) {
  const [facets, setFacets] = useState<Record<FacetKey, string>>({
    damage:   "Any",
    defense:  "Any",
    content:  "Any",
    budget:   "Any",
    playstyle:"Any",
    phase:    "All",
  });

  function setFacet(k: FacetKey, v: string) {
    setFacets(prev => ({ ...prev, [k]: v }));
  }

  return (
    <div className={styles.wrap}>

      {/* ── Featured editorial cards ─────────────────────────────────── */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Featured this league</h2>
        <div className={styles.featuredGrid}>
          {FEATURED.map(f => (
            <button key={f.title} className={styles.featuredCard} type="button">
              <span className={styles.featuredTag}>{f.tag}</span>
              <div className={styles.featuredTitle}>{f.title}</div>
              <div className={styles.featuredBlurb}>{f.blurb}</div>
            </button>
          ))}
        </div>
      </section>

      {middle}

      {/* ── Facet filters + sample results ───────────────────────────── */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Browse by what you want</h2>
        <div className={styles.facetRow}>
          {(Object.keys(FACETS) as FacetKey[]).map(k => (
            <div key={k} className={styles.facet}>
              <span className={styles.facetLabel}>{FACETS[k].label}</span>
              <select
                className={styles.facetSelect}
                value={facets[k]}
                onChange={(e) => setFacet(k, e.target.value)}
              >
                {FACETS[k].options.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          ))}
        </div>

        <div className={styles.resultsHint}>
          <strong>{SAMPLE_BUILDS.length} builds</strong> match — sorted by data confidence
        </div>

        <div className={styles.buildGrid}>
          {SAMPLE_BUILDS.map(b => (
            <button
              key={b.skill + b.ascendancy}
              className={styles.buildCard}
              type="button"
              onClick={() => onSelectBuild(b.skill, b.ascendancy)}
            >
              <div className={styles.buildSkill}>{b.skill}</div>
              <div className={styles.buildAsc}>{b.ascendancy}</div>
              <div className={styles.buildTags}>
                {b.exotic && <span className={`${styles.buildTag} ${styles.buildTagExotic}`}>Exotic</span>}
                {b.tags.map(t => <span key={t} className={styles.buildTag}>{t}</span>)}
                <span className={styles.buildTag}>n≈{b.n}</span>
              </div>
            </button>
          ))}
        </div>
      </section>

    </div>
  );
}
