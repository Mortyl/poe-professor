"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Navbar from "../../components/Navbar";
import BuildWizard from "../../components/BuildWizard";
import ArchetypeBrowser from "./components/ArchetypeBrowser";
import BrowseDiscovery from "./components/BrowseDiscovery";
import BuildGuideTome from "./components/BuildGuideTome";
import styles from "./page.module.css";

import type { BuildGuide } from "@/lib/types/builds";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type BuildMode = "browse" | "manual" | "random";

export default function BuildsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
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

  // Deep-link: ?skill=X&ascendancy=Y skips the wizard and jumps straight to
  // the build guide for that combo. Used by tier list cards. Only fires once
  // per mount — `deepLinkFiredRef` stops it re-firing if the user goes back
  // through "Build Another".
  const deepLinkFiredRef = useRef(false);


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
    setMode("browse");
  };

  useEffect(() => {
    if (deepLinkFiredRef.current) return;
    const skill = searchParams.get("skill");
    const ascendancy = searchParams.get("ascendancy");
    if (skill && ascendancy) {
      deepLinkFiredRef.current = true;
      setMode("manual");
      handleWizardComplete({
        skill,
        ascendancy,
        className: "",
        weapon: "",
        leagueType: "sc",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

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
            <BrowseDiscovery
              onSelectBuild={handleSelectBuild}
              middle={
                <ArchetypeBrowser
                  onBack={() => setMode("browse")}
                  onSelectBuild={handleSelectBuild}
                />
              }
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
            <button className={styles.resetBtn} style={{ marginTop: "32px" }} onClick={() => setMode("browse")}>
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
            <BuildWizard onComplete={handleWizardComplete} onBack={() => setMode("browse")} />
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
