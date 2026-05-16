"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "../components/Navbar";
import BuildWizard from "../components/BuildWizard";
import PassiveTreeCanvas from "./components/PassiveTreeCanvas";
import styles from "./page.module.css";

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
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type BuildMode = "select" | "manual" | "random";

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
    experienceLevel: "league_starter" | "endgame";
  } | null>(null);


  const handleWizardComplete = async (selections: {
    skill: string;
    ascendancy: string;
    className: string;
    weapon: string;
    leagueType: "sc" | "ssf" | "hc" | "hcssf";
    experienceLevel: "league_starter" | "endgame";
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
          experience_level: selections.experienceLevel,
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
                    <h3 className={styles.sectionTitle}>Key Skills</h3>
                    <ul className={styles.list}>
                      {guide.key_skills.map((s, i) => (
                        <li key={i} className={styles.listItem}>
                          <span className={styles.bullet}>▸</span>{s}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className={styles.section}>
                    <h3 className={styles.sectionTitle}>Gem Links</h3>
                    <ul className={styles.list}>
                      {guide.gem_links.map((g, i) => (
                        <li key={i} className={styles.listItem}>
                          <span className={styles.bullet}>▸</span>{g}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className={styles.section}>
                    <h3 className={styles.sectionTitle}>Gear Priorities</h3>
                    <ul className={styles.list}>
                      {guide.gear_priorities.map((g, i) => (
                        <li key={i} className={styles.listItem}>
                          <span className={styles.bullet}>▸</span>{g}
                        </li>
                      ))}
                    </ul>
                  </div>

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
                        highlightedNodes={guide.recommended_nodes}
                        optionalNodes={guide.optional_nodes ?? []}
                      />
                    </div>
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
