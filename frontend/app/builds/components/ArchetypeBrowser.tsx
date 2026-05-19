"use client";

import { useState, useEffect } from "react";
import wizardStyles from "../../components/wizard.module.css";
import styles from "./archetype.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Build {
  skill: string;
  ascendancy: string;
  builds_count: number;
  variant_companion: string;
  tag_signature: string;
  scraped: boolean;
}

interface Sub {
  id: string;
  label: string;
  builds: Build[];
  total: number;
  subsubs: Sub[] | null;
}

interface Archetype {
  id: string;
  label: string;
  icon: string;
  subs: Sub[];
  total_builds: number;
  combo_count: number;
}

interface BrowseResponse {
  archetypes: Archetype[];
  total: number;
  mode: string;
}

type BrowseMode = "league_starter" | "endgame";
type Step = "league" | "archetype" | "sub" | "subsub" | "build";

// ── Props ─────────────────────────────────────────────────────────────────────

interface Props {
  onSelectBuild: (skill: string, ascendancy: string) => void;
  onBack: () => void;
}

// ── Step labels ───────────────────────────────────────────────────────────────

const STEP_LABELS: Record<Step, string> = {
  league:    "League",
  archetype: "Archetype",
  sub:       "Style",
  subsub:    "Type",
  build:     "Build",
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function ArchetypeBrowser({ onSelectBuild, onBack }: Props) {
  const [step, setStep] = useState<Step>("league");
  const [mode, setMode] = useState<BrowseMode | null>(null);
  const [data, setData] = useState<BrowseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [selectedArch, setSelectedArch] = useState<Archetype | null>(null);
  const [selectedSub, setSelectedSub] = useState<Sub | null>(null);
  const [selectedSubSub, setSelectedSubSub] = useState<Sub | null>(null);

  // Build the visible step list dynamically based on what's been selected
  const visibleSteps: Step[] = (() => {
    const steps: Step[] = ["league", "archetype"];
    if (selectedArch && selectedArch.subs.length > 1) steps.push("sub");
    if (selectedSub && selectedSub.subsubs && selectedSub.subsubs.length > 0) steps.push("subsub");
    steps.push("build");
    return steps;
  })();

  const currentStepIndex = visibleSteps.indexOf(step);

  // Fetch when mode is chosen
  useEffect(() => {
    if (!mode) return;
    setLoading(true);
    setError("");
    fetch(`${API_URL}/api/builds/browse?mode=${mode}`)
      .then(r => r.json())
      .then((d: BrowseResponse) => setData(d))
      .catch(() => setError("Failed to load build data."))
      .finally(() => setLoading(false));
  }, [mode]);

  // ── Handlers ──

  const handleLeagueSelect = (m: BrowseMode) => {
    setMode(m);
    setSelectedArch(null);
    setSelectedSub(null);
    setSelectedSubSub(null);
    setStep("archetype");
  };

  const handleArchSelect = (arch: Archetype) => {
    setSelectedArch(arch);
    setSelectedSub(null);
    setSelectedSubSub(null);
    // Skip sub step if only one sub (or none)
    setStep(arch.subs.length > 1 ? "sub" : "build");
  };

  const handleSubSelect = (sub: Sub) => {
    setSelectedSub(sub);
    setSelectedSubSub(null);
    // Go to subsub step if this sub has children, else straight to builds
    setStep(sub.subsubs && sub.subsubs.length > 0 ? "subsub" : "build");
  };

  const handleSubSubSelect = (subsub: Sub) => {
    setSelectedSubSub(subsub);
    setStep("build");
  };

  const handleBack = () => {
    if (step === "league") { onBack(); return; }
    const prevStep = visibleSteps[currentStepIndex - 1];
    if (prevStep === "archetype") { setSelectedArch(null); setSelectedSub(null); setSelectedSubSub(null); }
    if (prevStep === "sub")       { setSelectedSub(null); setSelectedSubSub(null); }
    if (prevStep === "subsub")    { setSelectedSubSub(null); }
    setStep(prevStep);
  };

  const goToStep = (target: Step) => {
    const targetIndex = visibleSteps.indexOf(target);
    if (targetIndex >= currentStepIndex) return;
    if (targetIndex <= visibleSteps.indexOf("archetype")) { setSelectedArch(null); setSelectedSub(null); setSelectedSubSub(null); }
    else if (targetIndex <= visibleSteps.indexOf("sub"))  { setSelectedSub(null); setSelectedSubSub(null); }
    else if (targetIndex <= visibleSteps.indexOf("subsub")) { setSelectedSubSub(null); }
    setStep(target);
  };

  // ── Current builds ──

  const currentBuilds: Build[] = (() => {
    if (selectedSubSub) return selectedSubSub.builds;
    if (selectedSub) return selectedSub.builds;
    if (selectedArch && selectedArch.subs.length === 1) return selectedArch.subs[0].builds;
    return [];
  })();

  // ── Summary labels ──

  const summaryMode = mode === "league_starter" ? "League Starter" : mode === "endgame" ? "Endgame" : null;

  return (
    <div className={wizardStyles.wizard}>
      <button className={wizardStyles.backBtn} onClick={handleBack}>← Back</button>

      {/* Breadcrumb */}
      <div className={wizardStyles.breadcrumb}>
        {visibleSteps.map((s, i) => {
          const isComplete = i < currentStepIndex;
          const isCurrent = s === step;
          return (
            <div key={s} className={wizardStyles.breadcrumbItem}>
              <button
                className={[
                  wizardStyles.breadcrumbStep,
                  isCurrent  ? wizardStyles.breadcrumbCurrent : "",
                  isComplete ? wizardStyles.breadcrumbDone    : "",
                ].join(" ")}
                onClick={() => isComplete && goToStep(s)}
                disabled={!isComplete && !isCurrent}
              >
                <span className={wizardStyles.breadcrumbNum}>{i + 1}</span>
                <span className={wizardStyles.breadcrumbLabel}>{STEP_LABELS[s]}</span>
              </button>
              {i < visibleSteps.length - 1 && (
                <span className={`${wizardStyles.breadcrumbArrow} ${isComplete ? wizardStyles.breadcrumbArrowDone : ""}`}>›</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary */}
      {summaryMode && (
        <div className={wizardStyles.summary}>
          <span className={wizardStyles.summaryTag}>{summaryMode}</span>
          {selectedArch && <><span className={wizardStyles.summarySep}>·</span><span className={wizardStyles.summaryTag}>{selectedArch.label}</span></>}
          {selectedSub   && <><span className={wizardStyles.summarySep}>·</span><span className={wizardStyles.summaryTag}>{selectedSub.label}</span></>}
          {selectedSubSub && <><span className={wizardStyles.summarySep}>·</span><span className={wizardStyles.summaryTag}>{selectedSubSub.label}</span></>}
        </div>
      )}

      {/* Step content */}
      <div className={wizardStyles.stepContent}>

        {/* League */}
        {step === "league" && (
          <div className={wizardStyles.step}>
            <h2 className={wizardStyles.stepTitle}>Pick Your Goal</h2>
            <p className={wizardStyles.stepSubtitle}>Are you starting a new league or pushing endgame content?</p>
            <div className={styles.leagueGrid}>
              <button className={styles.leagueCard} onClick={() => handleLeagueSelect("league_starter")}>
                <span className={styles.leagueIcon}>🌱</span>
                <span className={styles.leagueName}>League Starter</span>
                <span className={styles.leagueDesc}>Builds that are strong from day one — budget-friendly and self-sufficient.</span>
              </button>
              <button className={styles.leagueCard} onClick={() => handleLeagueSelect("endgame")}>
                <span className={styles.leagueIcon}>⚔️</span>
                <span className={styles.leagueName}>Endgame</span>
                <span className={styles.leagueDesc}>High-investment builds including triggers and advanced mechanics.</span>
              </button>
            </div>
          </div>
        )}

        {/* Archetype */}
        {step === "archetype" && (
          <div className={wizardStyles.step}>
            {loading ? (
              <div className={styles.loadingRow}><div className={styles.spinner} /><span>Loading builds...</span></div>
            ) : error ? (
              <p className={styles.errorText}>{error}</p>
            ) : (
              <>
                <h2 className={wizardStyles.stepTitle}>Pick Your Archetype</h2>
                <p className={wizardStyles.stepSubtitle}>How do you want to play?</p>
                <div className={styles.archGrid}>
                  {data?.archetypes.map(arch => (
                    <button key={arch.id} className={styles.archCard} onClick={() => handleArchSelect(arch)}>
                      <span className={styles.archIcon}>{arch.icon}</span>
                      <span className={styles.archLabel}>{arch.label}</span>
                      <span className={styles.archCount}>{arch.combo_count} builds</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* Sub */}
        {step === "sub" && selectedArch && (
          <div className={wizardStyles.step}>
            <h2 className={wizardStyles.stepTitle}>Pick Your Style</h2>
            <p className={wizardStyles.stepSubtitle}>{selectedArch.label}</p>
            <div className={styles.subGrid}>
              {selectedArch.subs.map(sub => (
                <button key={sub.id} className={styles.subCard} onClick={() => handleSubSelect(sub)}>
                  <span className={styles.subLabel}>{sub.label}</span>
                  <span className={styles.subCount}>{sub.subsubs ? sub.subsubs.reduce((n, s) => n + s.builds.length, 0) : sub.builds.length} builds</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sub-sub */}
        {step === "subsub" && selectedSub && selectedSub.subsubs && (
          <div className={wizardStyles.step}>
            <h2 className={wizardStyles.stepTitle}>Pick Your Type</h2>
            <p className={wizardStyles.stepSubtitle}>{selectedArch?.label} · {selectedSub.label}</p>
            <div className={styles.subGrid}>
              {selectedSub.subsubs.map(subsub => (
                <button key={subsub.id} className={styles.subCard} onClick={() => handleSubSubSelect(subsub)}>
                  <span className={styles.subLabel}>{subsub.label}</span>
                  <span className={styles.subCount}>{subsub.builds.length} builds</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Build list */}
        {step === "build" && (
          <div className={wizardStyles.step}>
            <h2 className={wizardStyles.stepTitle}>Pick Your Build</h2>
            <p className={wizardStyles.stepSubtitle}>Ranked by popularity on poe.ninja</p>
            {currentBuilds.length === 0 ? (
              <p className={styles.emptyText}>No builds found in this category.</p>
            ) : (
              <div className={styles.buildList}>
                {currentBuilds.map((b, i) => (
                  <BuildRow
                    key={`${b.skill}-${b.ascendancy}-${b.variant_companion}-${i}`}
                    build={b}
                    rank={i + 1}
                    onSelect={onSelectBuild}
                  />
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}

// ── Build Row ─────────────────────────────────────────────────────────────────

function BuildRow({ build, rank, onSelect }: {
  build: Build;
  rank: number;
  onSelect: (skill: string, ascendancy: string) => void;
}) {
  const label = build.variant_companion
    ? `${build.skill} + ${build.variant_companion}`
    : build.skill;

  return (
    <button
      className={`${styles.buildRow} ${!build.scraped ? styles.buildRowPending : ""}`}
      onClick={() => onSelect(build.skill, build.ascendancy)}
      title={build.scraped ? "Full guide available" : "Build discovered — guide coming soon"}
    >
      <span className={styles.buildRank}>#{rank}</span>
      <div className={styles.buildMain}>
        <span className={styles.buildSkill}>{label}</span>
        <span className={styles.buildAsc}>{build.ascendancy}</span>
      </div>
      <div className={styles.buildMeta}>
        <span className={styles.buildCount}>{build.builds_count.toLocaleString()}</span>
        {!build.scraped && <span className={styles.buildPendingBadge}>Soon</span>}
      </div>
    </button>
  );
}
