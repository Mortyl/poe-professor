"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "../components/Navbar";
import BuildWizard from "../components/BuildWizard";
import ArchetypeBrowser from "./components/ArchetypeBrowser";
import BrowseDiscovery from "./components/BrowseDiscovery";
import BuildGuideTome from "./components/BuildGuideTome";
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
  const [mode, setMode] = useState<BuildMode>("browse");
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
    const handleSelectBuild = (skill: string, ascendancy: string) => {
      setMode("manual");
      handleWizardComplete({
        skill,
        ascendancy,
        className: "",
        weapon: "",
        leagueType: "sc",
      });
    };
    return (
      <>
        <Navbar />
        <main className={styles.main}>
          <div className={styles.browseContainer}>
            <header className={styles.browseHero}>
              <div className={styles.browseFlourish}>
                <span className={styles.browseFlourishLine} />
                <span className={styles.browseFlourishDiamond} />
                <span className={`${styles.browseFlourishDiamond} ${styles.browseFlourishCenter}`} />
                <span className={styles.browseFlourishDiamond} />
                <span className={styles.browseFlourishLine} />
              </div>
              <h1 className={styles.browseTitle}>BUILDS</h1>
              <p className={styles.browseSubtitle}>From the leaderboards of Wraeclast, made readable</p>
            </header>
            <BrowseDiscovery onSelectBuild={handleSelectBuild} />
            <ArchetypeBrowser
              onBack={() => setMode("select")}
              onSelectBuild={handleSelectBuild}
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

  // ── Build guide (editorial layout) ──
  if (guide) {
    return (
      <>
        <Navbar />
        <main className={styles.main}>
          <BuildGuideTome
            guide={guide}
            selectedMeta={selectedMeta}
            onReset={handleReset}
          />
        </main>
      </>
    );
  }

  // ── Manual wizard (class/asc/weapon/skill picker) ──
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

          {!loading && (
            <BuildWizard onComplete={handleWizardComplete} onBack={() => setMode("select")} />
          )}

          {loading && (
            <div className={styles.loading}>
              <div className={styles.spinner} />
              <p>Consulting the Professor...</p>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
