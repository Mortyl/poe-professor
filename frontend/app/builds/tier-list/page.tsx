"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "../../components/Navbar";
import styles from "./tier-list.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Mode = "composite" | "league_starter" | "endgame";
type Tier = "S" | "A" | "B" | "C" | "D";
const TIERS: Tier[] = ["S", "A", "B", "C", "D"];

interface TierBuild {
  skill: string;
  ascendancy: string;
  starter_count: number;
  endgame_count: number;
  retention_ratio: number | null;
  score: number;
  analysed: boolean;
}
interface ArchetypeBlock {
  id: string;
  label: string;
  icon: string;
  tiered: boolean;
  build_count: number;
  builds: TierBuild[];
  tiers: Record<Tier, TierBuild[]>;
}
interface TierListResponse {
  league: string;
  mode: Mode;
  total_combos: number;
  archetypes: ArchetypeBlock[];
}

const MODE_LABELS: Record<Mode, string> = {
  composite: "Composite",
  league_starter: "Starter Meta",
  endgame: "Endgame Meta",
};
const MODE_BLURBS: Record<Mode, string> = {
  composite: "Adoption × retention. Builds that grew from day-1 to endgame win.",
  league_starter: "Pure raw popularity in the first days of the league.",
  endgame: "What people are still playing weeks in, after the dust settles.",
};

function fmt(n: number) { return n.toLocaleString(); }

export default function TierListPage() {
  const [mode, setMode] = useState<Mode>("composite");
  const [data, setData] = useState<TierListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const r = await fetch(`${API_URL}/api/builds/tier-list?league=sc&mode=${mode}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (!cancelled) setData(json);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [mode]);

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.container}>

          <header className={styles.hero}>
            <div className={styles.flourish}>
              <span className={styles.flourishLine} />
              <span className={styles.flourishDiamond} />
              <span className={`${styles.flourishDiamond} ${styles.flourishCenter}`} />
              <span className={styles.flourishDiamond} />
              <span className={styles.flourishLine} />
            </div>
            <h1 className={styles.heroTitle}>TIER LIST</h1>
            <p className={styles.heroSubtitle}>
              The strongest builds this league, ranked by real player counts and endgame retention.
              No opinions — just data.
            </p>
          </header>

          <div className={styles.controls}>
            <div className={styles.modeToggle}>
              {(Object.keys(MODE_LABELS) as Mode[]).map((m) => (
                <button
                  key={m}
                  className={`${styles.modeBtn} ${mode === m ? styles.modeBtnActive : ""}`}
                  onClick={() => setMode(m)}
                >
                  {MODE_LABELS[m]}
                </button>
              ))}
            </div>
            <div className={styles.modeBlurb}>{MODE_BLURBS[mode]}</div>
          </div>

          {loading && <div className={styles.loading}>Consulting the data...</div>}
          {error && <div className={styles.error}>Failed to load tier list: {error}</div>}

          {data && data.archetypes.length === 0 && (
            <div className={styles.empty}>No build data has been collected yet for this league.</div>
          )}

          {data && data.archetypes.map((arch) => (
            <section key={arch.id} className={styles.archetype}>
              <header className={styles.archHead}>
                <h2 className={styles.archTitle}>
                  <span className={styles.archIcon} aria-hidden>{arch.icon}</span>
                  {arch.label}
                </h2>
                <span className={styles.archCount}>{arch.build_count} build{arch.build_count === 1 ? "" : "s"}</span>
              </header>

              {arch.tiered ? (
                <div className={styles.tierGrid}>
                  {TIERS.map((tier) => (
                    <div key={tier} className={`${styles.tierColumn} ${styles[`tier_${tier}`]}`}>
                      <div className={styles.tierBadge}>{tier}</div>
                      <div className={styles.tierBuilds}>
                        {arch.tiers[tier].length === 0 ? (
                          <div className={styles.tierEmpty}>—</div>
                        ) : (
                          arch.tiers[tier].map((b) => (
                            <BuildCard key={`${b.skill}|${b.ascendancy}`} build={b} mode={mode} />
                          ))
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div>
                  <div className={styles.lowSample}>Below the sample-size threshold for tiering — shown as a flat list.</div>
                  <div className={styles.flatRow}>
                    {arch.builds.map((b) => (
                      <BuildCard key={`${b.skill}|${b.ascendancy}`} build={b} mode={mode} />
                    ))}
                  </div>
                </div>
              )}
            </section>
          ))}

          {data && (
            <footer className={styles.legend}>
              Tiers from {fmt(data.total_combos)} combos across {data.archetypes.length} archetypes.
              <br />
              S = top 5% within archetype · A = top 15% · B / C / D = capped to top 4 each to keep the long tail readable.
            </footer>
          )}

        </div>
      </main>
    </>
  );
}

function BuildCard({ build, mode }: { build: TierBuild; mode: Mode }) {
  const primary = mode === "endgame" ? build.endgame_count : build.starter_count;
  const secondary = mode === "endgame" ? build.starter_count : build.endgame_count;
  const retentionLabel = build.retention_ratio !== null
    ? (build.retention_ratio >= 1.0
        ? `+${Math.round((build.retention_ratio - 1.0) * 100)}% retention`
        : `${Math.round((build.retention_ratio - 1.0) * 100)}% retention`)
    : null;
  const href = `/builds/find?skill=${encodeURIComponent(build.skill)}&ascendancy=${encodeURIComponent(build.ascendancy)}`;
  return (
    <Link
      href={href}
      className={`${styles.buildCard} ${!build.analysed ? styles.buildCardPending : ""}`}
      title={!build.analysed ? "Data pending — we know about this build but haven't run the deep scrape yet" : undefined}
    >
      <div className={styles.buildSkill}>{build.skill}</div>
      <div className={styles.buildAsc}>{build.ascendancy}</div>
      <div className={styles.buildStats}>
        <span title={mode === "endgame" ? "Endgame players" : "League starter players"}>
          {fmt(primary)}
        </span>
        {secondary > 0 && (
          <span className={styles.buildStatSecondary} title={mode === "endgame" ? "League starter players" : "Endgame players"}>
            / {fmt(secondary)}
          </span>
        )}
      </div>
      {retentionLabel && (
        <div className={`${styles.buildRetention} ${(build.retention_ratio ?? 0) >= 1 ? styles.retentionPos : styles.retentionNeg}`}>
          {retentionLabel}
        </div>
      )}
      {!build.analysed && (
        <div className={styles.buildPendingBadge}>data pending</div>
      )}
    </Link>
  );
}
