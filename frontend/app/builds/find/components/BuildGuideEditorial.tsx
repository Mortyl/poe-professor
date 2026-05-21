"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import GemLinksPanel from "./GemLinksPanel";
import { skillIconPath, ascendancyIconPath, skillInitial } from "@/lib/icons";
import styles from "./editorial.module.css";

// ── Shared types — mirror the BuildGuide shape from page.tsx ────────────────
interface GemEntry { name: string; pct: number; }
interface SkillGem { name: string; pct: number; supports: GemEntry[]; }
interface GemLinkData { main_skill: string; skill_gems: SkillGem[]; builds_analysed: number; }
interface UniqueItem { name: string; base: string; slot: string; pct: number; }
interface GearSlot {
  slot: string;
  top_unique: UniqueItem | null;
  top_rare_base: string;
  top_rare_base_pct: number;
  top_mods: string[];
}
interface GearData { builds_analysed: number; slots: GearSlot[]; }

interface BuildGuide {
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
  pob_provenance: { snapshot: string; level: number; node_overlap: number; support_overlap: number; supports_rewritten: boolean } | null;
  data_pending: boolean;
}

interface SelectedMeta {
  skill: string;
  ascendancy: string;
  className: string;
  weapon: string;
  leagueType: "sc" | "ssf" | "hc" | "hcssf";
}

interface Props {
  guide: BuildGuide;
  selectedMeta: SelectedMeta | null;
  onReset: () => void;
}

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "gems",     label: "Gem Links" },
  { id: "play",     label: "Playstyle" },
];

// Builds-analysed comes from whichever data block actually has it
function buildsAnalysed(guide: BuildGuide): number {
  return (
    guide.gem_link_data?.builds_analysed
    ?? guide.gear_data_life?.builds_analysed
    ?? guide.gear_data_es?.builds_analysed
    ?? 0
  );
}

export default function BuildGuideEditorial({ guide, selectedMeta, onReset }: Props) {
  const [activeSection, setActiveSection] = useState<string>("overview");
  const [skillIconOk, setSkillIconOk] = useState(true);
  const [ascIconOk, setAscIconOk] = useState(true);

  // Scroll-spy: highlight the section nearest the top of the viewport.
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter(e => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveSection(visible[0].target.id);
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: 0 },
    );
    SECTIONS.forEach(s => {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  const n = buildsAnalysed(guide);

  return (
    <div className={styles.wrap}>

      <div className={styles.crumbs}>
        <Link href="/builds">Builds</Link>
        <span className={styles.sep}>›</span>
        {guide.ascendancy}
        <span className={styles.sep}>›</span>
        {guide.skill}
      </div>

      <header className={styles.hero}>
        <div className={styles.heroText}>
          <span className={styles.heroTag}>
            {selectedMeta?.className ? `${selectedMeta.className} · ` : ""}{guide.ascendancy}
          </span>
          <h1 className={styles.heroName}>{guide.skill}</h1>
          {guide.overview && <p className={styles.heroSub}>{guide.overview}</p>}
          <div className={styles.heroMeta}>
            {n > 0 && <span>Analysed<strong>{n.toLocaleString()}</strong></span>}
            {selectedMeta?.weapon && <span>Weapon<strong>{selectedMeta.weapon}</strong></span>}
            {selectedMeta?.className && <span>Class<strong>{selectedMeta.className}</strong></span>}
            {guide.recommended_nodes?.length > 0 && (
              <span>Tree<strong>{guide.recommended_nodes.length} nodes</strong></span>
            )}
          </div>
          {guide.disclaimer && <div className={styles.disclaimer}>{guide.disclaimer}</div>}
        </div>
        <div className={styles.heroArt}>
          <div className={styles.heroAsc} title={guide.ascendancy}>
            {ascIconOk ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={ascendancyIconPath(guide.ascendancy)}
                alt={guide.ascendancy}
                className={styles.heroAscImg}
                onError={() => setAscIconOk(false)}
              />
            ) : (
              <span className={styles.heroAscFallback}>{guide.ascendancy}</span>
            )}
          </div>
          <div className={styles.heroSkill} title={guide.skill}>
            {skillIconOk ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={skillIconPath(guide.skill)}
                alt={guide.skill}
                className={styles.heroSkillImg}
                onError={() => setSkillIconOk(false)}
              />
            ) : (
              <span className={styles.heroSkillFallback}>{skillInitial(guide.skill)}</span>
            )}
          </div>
        </div>
      </header>

      <div className={styles.body}>

        <aside className={styles.side}>
          <div className={styles.sideCard}>
            <div className={styles.sideLabel}>Quick Stats</div>
            <div className={styles.sideRow}>
              <span className={styles.k}>Ascendancy</span>
              <span className={styles.v}>{guide.ascendancy}</span>
            </div>
            {selectedMeta?.className && (
              <div className={styles.sideRow}>
                <span className={styles.k}>Class</span>
                <span className={styles.v}>{selectedMeta.className}</span>
              </div>
            )}
            {selectedMeta?.weapon && (
              <div className={styles.sideRow}>
                <span className={styles.k}>Weapon</span>
                <span className={styles.v}>{selectedMeta.weapon}</span>
              </div>
            )}
            {n > 0 && (
              <div className={styles.sideRow}>
                <span className={styles.k}>Builds</span>
                <span className={styles.v}>{n.toLocaleString()}</span>
              </div>
            )}
            {guide.recommended_nodes?.length > 0 && (
              <div className={styles.sideRow}>
                <span className={styles.k}>Tree Points</span>
                <span className={styles.v}>{guide.recommended_nodes.length}</span>
              </div>
            )}
          </div>

          <div className={styles.sideCard}>
            <div className={styles.sideLabel}>On this page</div>
            <div className={styles.navList}>
              {SECTIONS.map(s => (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  className={activeSection === s.id ? styles.active : ""}
                >
                  {s.label}
                </a>
              ))}
            </div>
          </div>

          <button className={styles.backLink} onClick={onReset}>← Build Another</button>
        </aside>

        <div className={styles.main}>

          <section id="overview" className={styles.section}>
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle}>Overview</h2>
            </div>
            <div className={styles.prose}>
              {guide.overview ? <p>{guide.overview}</p> : (
                <p className={styles.empty}>No overview written for this build yet.</p>
              )}
              {guide.passive_tree_notes && guide.passive_tree_notes !== guide.overview && (
                <p>{guide.passive_tree_notes}</p>
              )}
            </div>
          </section>

          <section id="gems" className={styles.section}>
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle}>Gem Links</h2>
              {guide.gem_link_data && (
                <span className={styles.sectionSub}>
                  Based on {guide.gem_link_data.builds_analysed.toLocaleString()} builds
                </span>
              )}
            </div>
            {guide.gem_link_data ? (
              <GemLinksPanel data={guide.gem_link_data} />
            ) : (
              <p className={styles.empty}>No gem link data available for this build yet.</p>
            )}
          </section>


          <section id="play" className={styles.section}>
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle}>Playstyle</h2>
            </div>
            <div className={styles.prose}>
              {guide.playstyle_tips ? (
                <p>{guide.playstyle_tips}</p>
              ) : (
                <p className={styles.empty}>No playstyle tips written for this build yet.</p>
              )}
            </div>
          </section>

        </div>
      </div>
    </div>
  );
}
