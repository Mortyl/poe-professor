"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import GearPanel from "./GearPanel";
import PassiveTreeCanvas from "./PassiveTreeCanvasPixi";
import AscendancyWidget from "./AscendancyWidget";
import { itemIconPath, skillInitial } from "./icons";
import styles from "./tome.module.css";

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

// Which slots get featured in the tome's compact gear list.
// (Full doll with everything else still renders below the tome.)
const TOME_GEAR_SLOTS = ["Helmet", "Body Armour", "Weapon 1", "Weapon 2", "Gloves", "Boots"];

const LEAGUE_LABELS: Record<string, string> = {
  sc:    "Softcore",
  ssf:   "Solo Self-Found",
  hc:    "Hardcore",
  hcssf: "Hardcore SSF",
};

function buildsAnalysed(guide: BuildGuide): number {
  return (
    guide.gem_link_data?.builds_analysed
    ?? guide.gear_data_life?.builds_analysed
    ?? guide.gear_data_es?.builds_analysed
    ?? 0
  );
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

export default function BuildGuideTome({ guide, selectedMeta, onReset }: Props) {
  const [gearTab, setGearTab] = useState<"life" | "es">("life");
  const hasLife = !!guide.gear_data_life;
  const hasEs   = !!guide.gear_data_es;
  const gearData    = gearTab === "life" ? guide.gear_data_life : guide.gear_data_es;
  const gearUniques = gearTab === "life" ? guide.useful_uniques : guide.useful_uniques_es;

  // Default to whichever variant has data
  useEffect(() => {
    if (!hasLife && hasEs) setGearTab("es");
  }, [hasLife, hasEs]);

  const n = buildsAnalysed(guide);
  const tomeGearRows = (gearData?.slots ?? []).filter(s => TOME_GEAR_SLOTS.includes(s.slot));
  // Sort tome gear rows in the order of TOME_GEAR_SLOTS, not the API order
  tomeGearRows.sort((a, b) => TOME_GEAR_SLOTS.indexOf(a.slot) - TOME_GEAR_SLOTS.indexOf(b.slot));
  const topGemGroups = guide.gem_link_data?.skill_gems?.slice(0, 3) ?? [];

  const playstyleParas = guide.playstyle_tips
    ? guide.playstyle_tips.split(/\n\n+/).filter(p => p.trim().length > 0)
    : [];

  const leagueLabel = selectedMeta?.leagueType
    ? (LEAGUE_LABELS[selectedMeta.leagueType] ?? selectedMeta.leagueType.toUpperCase())
    : null;

  return (
    <div className={styles.wrap}>

      {/* Breadcrumb */}
      <div className={styles.crumbs}>
        <Link href="/builds">Builds</Link>
        <span className={styles.sep}>›</span>
        <span>{guide.ascendancy}</span>
        <span className={styles.sep}>›</span>
        <span>{guide.skill}</span>
      </div>

      {/* ── TOME ─────────────────────────────────────────────────────── */}
      <div className={styles.tome}>

        {/* Left page: story */}
        <div className={styles.page}>
          <div className={styles.pageNumber}>Prologue</div>

          {leagueLabel && <span className={styles.heroTag}>{leagueLabel}</span>}
          <h1 className={styles.heroName}>{guide.skill}</h1>
          <p className={styles.heroSub}>
            {[selectedMeta?.className, guide.ascendancy, selectedMeta?.weapon].filter(Boolean).join(" · ")}
          </p>

          <div className={styles.flourish}>
            <span className={styles.line} />
            <span className={styles.diamond} />
            <span className={`${styles.diamond} ${styles.diamondCenter}`} />
            <span className={styles.diamond} />
            <span className={styles.line} />
          </div>

          <div className={styles.story}>
            {guide.overview
              ? <p>{guide.overview}</p>
              : <p>This build has not been narrated yet.</p>}
          </div>

          {playstyleParas.length > 0 && (
            <>
              <div className={styles.storySub}>How it plays</div>
              <div className={styles.story}>
                {playstyleParas.map((p, i) => <p key={i}>{p}</p>)}
              </div>
            </>
          )}

          <div className={styles.storySub}>Tagged As</div>
          <div className={styles.pillRow}>
            {selectedMeta?.className && (
              <span className={`${styles.pill} ${styles.pillOn}`}>{selectedMeta.className}</span>
            )}
            {guide.ascendancy && (
              <span className={`${styles.pill} ${styles.pillOn}`}>{guide.ascendancy}</span>
            )}
            {selectedMeta?.weapon && (
              <span className={`${styles.pill} ${styles.pillOn}`}>{selectedMeta.weapon}</span>
            )}
            {leagueLabel && (
              <span className={`${styles.pill} ${styles.pillOn}`}>{leagueLabel}</span>
            )}
          </div>

          {guide.ascendancy && (
            <>
              <div className={styles.storySub}>Ascendancy</div>
              <div style={{ marginTop: "8px" }}>
                <AscendancyWidget
                  className={selectedMeta?.className}
                  ascendancy={guide.ascendancy}
                  highlightedNodes={guide.recommended_nodes}
                  optionalNodes={guide.optional_nodes ?? []}
                  ascNodes={guide.asc_nodes ?? []}
                />
              </div>
            </>
          )}
        </div>

        {/* Spine */}
        <div className={styles.spine} />

        {/* Right page: data */}
        <div className={styles.page}>
          <div className={styles.pageNumber}>The Data</div>

          {n > 0 && (
            <span className={styles.dataLabel}>From {n.toLocaleString()} Real Builds</span>
          )}
          <div className={styles.dataMeta}>
            {selectedMeta?.className && (
              <span>Class<strong>{selectedMeta.className}</strong></span>
            )}
            <span>Ascendancy<strong>{guide.ascendancy}</strong></span>
            {guide.recommended_nodes.length > 0 && (
              <span>Tree<strong>{guide.recommended_nodes.length} nodes</strong></span>
            )}
          </div>

          {/* Gem Links (top 3) */}
          {topGemGroups.length > 0 && (
            <>
              <div className={styles.subhead}>
                <span>Gem Links</span>
                {guide.gem_link_data && (
                  <span className={styles.sourceN}>
                    n = {guide.gem_link_data.builds_analysed.toLocaleString()}
                  </span>
                )}
              </div>
              {topGemGroups.map((skill, i) => (
                <div key={i} className={styles.gem}>
                  <div className={styles.gemHead}>
                    <span className={styles.gemBubble}>{skillInitial(skill.name)}</span>
                    <span className={styles.skillName}>{skill.name}</span>
                    <span className={styles.skillPct}>{skill.pct.toFixed(0)}%</span>
                  </div>
                  <div className={styles.supports}>
                    {skill.supports
                      .filter(s => s.pct >= 20)
                      .slice(0, 4)
                      .map((s, j) => (
                        <span key={j} className={styles.support}>
                          <span className={styles.supportDot}>{skillInitial(s.name)}</span>
                          {truncate(s.name, 16)}
                          <span className={styles.supportPct}>{s.pct.toFixed(0)}%</span>
                        </span>
                      ))}
                  </div>
                </div>
              ))}
            </>
          )}

          {/* Gear highlights */}
          {tomeGearRows.length > 0 && gearData && (
            <>
              <div className={styles.subhead}>
                <span>Gear · {gearTab === "life" ? "Life" : "Energy Shield"}</span>
                <span className={styles.sourceN}>n = {gearData.builds_analysed.toLocaleString()}</span>
              </div>
              {tomeGearRows.map((slot, i) => {
                const useUnique = !!slot.top_unique;
                const itemName  = useUnique ? slot.top_unique!.name : slot.top_rare_base;
                const baseName  = useUnique ? slot.top_unique!.base : "Rare";
                const pct       = useUnique ? slot.top_unique!.pct : slot.top_rare_base_pct;
                const iconSrc   = itemIconPath(itemName, baseName);
                return (
                  <div key={i} className={styles.gearRow}>
                    <div className={styles.gearIcon}>
                      {iconSrc && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={iconSrc} alt="" width={36} height={36} />
                      )}
                    </div>
                    <span className={styles.slotName}>{slot.slot}</span>
                    <div>
                      <span className={`${styles.itemName} ${useUnique ? styles.itemNameUnique : ""}`}>
                        {itemName || "—"}
                      </span>
                      <span className={styles.itemBase}>
                        {baseName}{pct !== undefined && pct > 0 ? ` · ${pct.toFixed(0)}%` : ""}
                      </span>
                    </div>
                  </div>
                );
              })}
            </>
          )}

          {/* Tree thumb + link */}
          {guide.recommended_nodes.length > 0 && (
            <>
              <div className={styles.subhead}>
                <span>Passive Tree</span>
                <span className={styles.sourceN}>
                  {guide.recommended_nodes.length} core · {guide.optional_nodes.length} opt
                </span>
              </div>
              <div className={styles.treeThumb}>— tree preview —</div>
              <a href="#full-tree" className={styles.openTree}>Open Full Tree →</a>
            </>
          )}
        </div>
      </div>

      {/* ── Detail sections below the tome ──────────────────────────── */}

      <section id="full-tree" className={styles.detailSection}>
        <h2 className={styles.detailTitle}>Passive Tree</h2>
        <PassiveTreeCanvas
          className={selectedMeta?.className}
          ascendancy={guide.ascendancy}
          highlightedNodes={guide.recommended_nodes}
          optionalNodes={guide.optional_nodes ?? []}
        />
        {guide.recommended_nodes.length > 0 && (
          <div className={styles.treeLegend}>
            <span><span className={styles.dot} style={{ background: "#e8c84a" }} />Mandatory</span>
            <span><span className={styles.dot} style={{ background: "#4ab8cc" }} />Optional</span>
          </div>
        )}

        {selectedMeta?.className && guide.ascendancy && (
          <div style={{ marginTop: "32px" }}>
            <AscendancyWidget
              className={selectedMeta.className}
              ascendancy={guide.ascendancy}
              highlightedNodes={guide.recommended_nodes}
              optionalNodes={guide.optional_nodes ?? []}
              ascNodes={guide.asc_nodes ?? []}
            />
          </div>
        )}
      </section>

      {gearData && (
        <section className={styles.detailSection}>
          <h2 className={styles.detailTitle}>Gear</h2>
          {hasLife && hasEs && (
            <div className={styles.gearTabs}>
              <button
                onClick={() => setGearTab("life")}
                className={`${styles.gearTab} ${gearTab === "life" ? styles.gearTabActive : ""}`}
              >
                Life
              </button>
              <button
                onClick={() => setGearTab("es")}
                className={`${styles.gearTab} ${gearTab === "es" ? styles.gearTabActive : ""}`}
              >
                Energy Shield
              </button>
            </div>
          )}
          <GearPanel data={gearData} usefulUniques={gearUniques ?? []} />
        </section>
      )}

      {guide.disclaimer && (
        <div className={styles.disclaimer}>{guide.disclaimer}</div>
      )}

      <div className={styles.actions}>
        <button className={styles.backButton} onClick={onReset}>← Build Another</button>
      </div>
    </div>
  );
}
