"use client";

import { useState } from "react";
import type React from "react";
import { useRouter } from "next/navigation";
import Navbar from "../components/Navbar";
import BuildWizard from "../components/BuildWizard";
import ArchetypeBrowser from "./components/ArchetypeBrowser";
import PassiveTreeCanvas, { AscendancyCanvas } from "./components/PassiveTreeCanvas";
import GemLinksPanel from "./components/GemLinksPanel";
import GearPanel from "./components/GearPanel";
import styles from "./page.module.css";

interface GemEntry {
  name: string;
  pct: number;
}

interface SkillGem {
  name: string;
  pct: number;
  supports: GemEntry[];
}

interface GemLinkData {
  main_skill: string;
  skill_gems: SkillGem[];
  builds_analysed: number;
}

interface UniqueItem {
  name: string;
  base: string;
  slot: string;
  pct: number;
}

interface GearSlot {
  slot: string;
  top_unique: UniqueItem | null;
  top_rare_base: string;
  top_rare_base_pct: number;
  top_mods: string[];
}

interface GearData {
  builds_analysed: number;
  slots: GearSlot[];
}

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

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type BuildMode = "select" | "browse" | "manual" | "random";

export default function BuildsPage() {
  const router = useRouter();
  const [mode, setMode] = useState<BuildMode>("select");
  const [guide, setGuide] = useState<BuildGuide | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedMeta, setSelectedMeta] = useState<{
    skill: string;
    ascendancy: string;
    className: string;
    weapon: string;
    leagueType: "sc" | "ssf" | "hc" | "hcssf";
  } | null>(null);


  const handleWizardComplete = async (selections: {
    skill: string;
    ascendancy: string;
    className: string;
    weapon: string;
    leagueType: "sc" | "ssf" | "hc" | "hcssf";
  }) => {
    setSelectedMeta(selections);
    setLoading(true);
    setError("");
    setGuide(null);

    try {
      const res = await fetch(`${API_URL}/api/builds/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skill: selections.skill,
          ascendancy: selections.ascendancy,
          weapon_type: selections.weapon,
          class_name: selections.className,
          league_type: selections.leagueType,
        }),
      });
      if (!res.ok) throw new Error("Failed to generate build");
      const data = await res.json();
      setGuide(data);
    } catch {
      setError("Failed to generate build guide. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setGuide(null);
    setError("");
    setSelectedMeta(null);
    setMode("select");
  };

  // ── Mode select screen ──
  if (mode === "select") {
    return (
      <>
        <Navbar />
        <main className={styles.main}>
          <div className={styles.modeSelect}>
            <button className={styles.modeBackBtn} onClick={() => router.push("/")}>
              ← Back
            </button>
            <p className={styles.eyebrow}>Path of Exile 2 · Build Creator</p>
            <h1 className={styles.title}>How shall we begin?</h1>
            <div className={styles.modeButtons}>
              <button className={`${styles.modeBtn} ${styles.modeBtnBrowse}`} onClick={() => setMode("browse")}>
                <span className={styles.modeIcon}>📖</span>
                <span className={styles.modeName}>Browse Builds</span>
                <span className={styles.modeDesc}>Explore meta builds by archetype — bow, spell, melee, minion and more.</span>
              </button>
              <button className={styles.modeBtn} onClick={() => setMode("manual")}>
                <span className={styles.modeIcon}>⚔️</span>
                <span className={styles.modeName}>You Decide</span>
                <span className={styles.modeDesc}>Choose your class, ascendancy, weapon and skill manually.</span>
              </button>
              <button className={`${styles.modeBtn} ${styles.modeBtnFate}`} onClick={() => setMode("random")}>
                <span className={styles.modeIcon}>🎲</span>
                <span className={styles.modeName}>Fate Decides</span>
                <span className={styles.modeDesc}>Spin the wheel — let chance determine your destiny, exile.</span>
              </button>
            </div>
          </div>
        </main>
      </>
    );
  }

  // ── Browse builds ──
  if (mode === "browse") {
    return (
      <>
        <Navbar />
        <main className={styles.main}>
          <div className={styles.header}>
            <div className={styles.headerInner}>
              <p className={styles.eyebrow}>Path of Exile 2 · Build Browser</p>
              <h1 className={styles.title}>Browse Builds</h1>
              <p className={styles.subtitle}>
                Meta builds sourced from poe.ninja — select an archetype to explore
              </p>
            </div>
          </div>
          <div className={styles.content}>
            <ArchetypeBrowser
              onBack={() => setMode("select")}
              onSelectBuild={(skill, ascendancy) => {
                setMode("manual");
                handleWizardComplete({
                  skill,
                  ascendancy,
                  className: "",
                  weapon: "",
                  leagueType: "sc",
                });
              }}
            />
          </div>
        </main>
      </>
    );
  }

  // ── Fate decides — placeholder ──
  if (mode === "random") {
    return (
      <>
        <Navbar />
        <main className={styles.main}>
          <div className={styles.modeSelect}>
            <p className={styles.eyebrow}>Path of Exile 2 · Build Creator</p>
            <h1 className={styles.title}>Fate Decides</h1>
            <p className={styles.subtitle} style={{ textAlign: "center", marginTop: "12px" }}>
              The randomiser is coming soon, exile.
            </p>
            <button className={styles.resetBtn} style={{ marginTop: "32px" }} onClick={() => setMode("select")}>
              ← Back
            </button>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.header}>
          <div className={styles.headerInner}>
            <p className={styles.eyebrow}>Path of Exile 2 · AI Powered</p>
            <h1 className={styles.title}>Build Guide Generator</h1>
            <p className={styles.subtitle}>
              Choose your class, ascendancy, weapon and skill to generate a personalised build guide
            </p>
          </div>
        </div>

        <div className={styles.content}>
          {error && <div className={styles.error}>{error}</div>}

          {!guide && !loading && (
            <BuildWizard onComplete={handleWizardComplete} onBack={() => setMode("select")} />
          )}

          {loading && (
            <div className={styles.loading}>
              <div className={styles.spinner} />
              <p>Consulting the Professor...</p>
            </div>
          )}

          {guide && (
            <>
              <button className={styles.resetBtn} onClick={handleReset}>
                ← Build Another
              </button>

              <div className={styles.guide}>
                <div className={styles.guideHeader}>
                  <h2 className={styles.guideName}>{guide.skill}</h2>
                  <span className={styles.guideAsc}>{guide.ascendancy}</span>
                  {selectedMeta && (
                    <span className={styles.guideWeapon}>{selectedMeta.weapon}</span>
                  )}
                </div>

                <div className={styles.disclaimer}>{guide.disclaimer}</div>

                <div className={styles.sections}>
                  <div className={styles.section}>
                    <h3 className={styles.sectionTitle}>Overview</h3>
                    <p className={styles.sectionText}>{guide.overview}</p>
                  </div>

                  <div className={styles.section}>
                    <h3 className={styles.sectionTitle}>Gem Links</h3>
                    {guide.gem_link_data ? (
                      <GemLinksPanel data={guide.gem_link_data} />
                    ) : (
                      <p className={styles.sectionText} style={{ color: "#666" }}>
                        No gem link data available for this build yet.
                      </p>
                    )}
                  </div>

                  {(guide.gear_data_life || guide.gear_data_es) && (
                    <GearSection guide={guide} />
                  )}

                  <div className={styles.section}>
                    <h3 className={styles.sectionTitle}>Passive Tree</h3>
                    <p className={styles.sectionText}>{guide.passive_tree_notes}</p>
                    {guide.recommended_nodes.length > 0 && (
                      <div style={{ display: "flex", gap: "16px", marginTop: "10px", marginBottom: "4px", fontSize: "12px" }}>
                        <span style={{ color: "#e8c84a" }}>&#9679; Mandatory</span>
                        <span style={{ color: "#4ab8cc" }}>&#9679; Optional</span>
                      </div>
                    )}
                    <div style={{ marginTop: "8px" }}>
                      <PassiveTreeCanvas
                        className={selectedMeta?.className}
                        ascendancy={guide.ascendancy}
                        highlightedNodes={guide.recommended_nodes}
                        optionalNodes={guide.optional_nodes ?? []}
                      />
                    </div>

                    {selectedMeta?.ascendancy && (
                      <div style={{ marginTop: "16px", display: "flex", alignItems: "flex-start", gap: "24px" }}>
                        {/* Legend — left */}
                        <div style={{ flex: "0 0 auto", paddingTop: "4px" }}>
                          <h4 style={{ fontSize: "12px", color: "#666", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "12px", fontFamily: "var(--font-cinzel, serif)" }}>
                            Ascendancy Order
                          </h4>
                          {[
                            { label: "1st", colour: "#e8c84a" },
                            { label: "2nd", colour: "#4a9a5a" },
                            { label: "3rd", colour: "#4a7acc" },
                            { label: "4th", colour: "#cc4444" },
                          ].map(({ label, colour }) => (
                            <div key={label} style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                              <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: colour, display: "inline-block", flexShrink: 0 }} />
                              <span style={{ fontSize: "13px", color: colour, fontFamily: "var(--font-cinzel, serif)" }}>{label}</span>
                            </div>
                          ))}
                        </div>

                        {/* Canvas — right */}
                        <AscendancyCanvas
                          className={selectedMeta.className}
                          ascendancy={guide.ascendancy}
                          highlightedNodes={guide.recommended_nodes}
                          optionalNodes={guide.optional_nodes ?? []}
                          ascNodes={guide.asc_nodes ?? []}
                        />
                      </div>
                    )}
                  </div>

                  <div className={styles.section}>
                    <h3 className={styles.sectionTitle}>Playstyle Tips</h3>
                    <p className={styles.sectionText}>{guide.playstyle_tips}</p>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}

function GearSection({ guide }: { guide: BuildGuide }) {
  const [tab, setTab] = useState<"life" | "es">("life");
  const hasEs = !!guide.gear_data_es;

  const gearData    = tab === "life" ? guide.gear_data_life    : guide.gear_data_es;
  const uniques     = tab === "life" ? guide.useful_uniques     : guide.useful_uniques_es;

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: "4px 14px",
    fontSize: "11px",
    fontFamily: "var(--font-cinzel, serif)",
    letterSpacing: "0.05em",
    background: active ? "#2a1e0e" : "transparent",
    border: `1px solid ${active ? "#6a5030" : "#2a2010"}`,
    borderRadius: "3px",
    color: active ? "#c8a84a" : "#555",
    cursor: "pointer",
  });

  return (
    <>
      {gearData && (
        <div className={styles.section}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
            <h3 className={styles.sectionTitle} style={{ margin: 0 }}>Gear</h3>
            {hasEs && (
              <div style={{ display: "flex", gap: "4px" }}>
                <button style={tabStyle(tab === "life")} onClick={() => setTab("life")}>Life</button>
                <button style={tabStyle(tab === "es")}   onClick={() => setTab("es")}>Energy Shield</button>
              </div>
            )}
          </div>
          <GearPanel data={gearData} usefulUniques={uniques ?? []} />
        </div>
      )}
    </>
  );
}
