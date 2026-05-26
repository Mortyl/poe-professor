"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import GearPanel from "./GearPanel";
import PassiveTreeCanvas from "./PassiveTreeCanvasPixi";
import AscendancyWidget from "./AscendancyWidget";
import { itemIconPath, skillInitial } from "@/lib/icons";
import styles from "./tome.module.css";

import type { BuildGuide, SelectedMeta } from "@/lib/types/builds";

interface Props {
  guide: BuildGuide;
  selectedMeta: SelectedMeta | null;
  onReset: () => void;
}

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
  const { data: session } = useSession();
  const router = useRouter();

  const [gearTab, setGearTab] = useState<"life" | "es">("life");
  const [pobCopied, setPobCopied] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  const shareGuide = async () => {
    if (typeof window === "undefined") return;
    const url = `${window.location.origin}/builds/find`
      + `?skill=${encodeURIComponent(guide.skill)}`
      + `&ascendancy=${encodeURIComponent(guide.ascendancy)}`;
    try {
      await navigator.clipboard.writeText(url);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 1800);
    } catch {
      window.prompt("Copy this share link:", url);
    }
  };

  // Save-guide UI state
  const [savePanelOpen, setSavePanelOpen] = useState(false);
  const [saveLabel, setSaveLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<null | "saved" | "deduped" | "error">(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleSaveGuide = async () => {
    if (!session?.user) {
      const target = `/builds/find?skill=${encodeURIComponent(guide.skill)}&ascendancy=${encodeURIComponent(guide.ascendancy)}`;
      router.push(`/auth/signin?callbackUrl=${encodeURIComponent(target)}`);
      return;
    }
    setSaving(true);
    setSaveStatus(null);
    setSaveError(null);
    try {
      const r = await fetch("/api/me/builds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skill: guide.skill,
          ascendancy: guide.ascendancy,
          className: selectedMeta?.className ?? null,
          leagueType: selectedMeta?.leagueType ?? "sc",
          label: saveLabel.trim() || null,
        }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({ error: "Unknown error" }));
        throw new Error(e.error ?? r.statusText);
      }
      const data = await r.json();
      setSaveStatus(data.deduped ? "deduped" : "saved");
      setSaveLabel("");
      // Auto-close the panel after a beat
      setTimeout(() => setSavePanelOpen(false), 2200);
    } catch (e) {
      setSaveStatus("error");
      setSaveError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const copyPob = async () => {
    if (!guide.pob_export) return;
    try {
      await navigator.clipboard.writeText(guide.pob_export);
      setPobCopied(true);
      setTimeout(() => setPobCopied(false), 1800);
    } catch {
      // Clipboard API can fail on insecure contexts — silently ignore
    }
  };
  const hasLife = !!guide.gear_data_life;
  const hasEs   = !!guide.gear_data_es;

  // Level-bucket toggle: 'all' shows the legacy life/es totals, 'early' and
  // 'late' show the per-bucket sub-reports (endgame only — buckets carry
  // separately analysed gear for lvl 80-95 vs lvl 96+ cohorts).
  type LevelView = "all" | "early" | "late";
  const [levelView, setLevelView] = useState<LevelView>("all");
  const hasEarly = !!guide.level_buckets?.early;
  const hasLate  = !!guide.level_buckets?.late;
  const hasBucketToggle = hasEarly || hasLate;

  const bucketSection = (
    levelView === "early" ? guide.level_buckets?.early :
    levelView === "late"  ? guide.level_buckets?.late  :
    null
  );

  // Resolve the active gear data: prefer the bucket section if user is on
  // early/late, else fall back to the legacy life/es. If the bucket doesn't
  // have data for the current life/es tab, fall back to the legacy too.
  const gearData = (
    bucketSection
      ? (gearTab === "life" ? bucketSection.life : bucketSection.es)
        ?? (gearTab === "life" ? guide.gear_data_life : guide.gear_data_es)
      : (gearTab === "life" ? guide.gear_data_life : guide.gear_data_es)
  );
  // useful_uniques aren't bucketed yet — keep them tied to life/es view
  const gearUniques = gearTab === "life" ? guide.useful_uniques : guide.useful_uniques_es;

  const bucketLabel = (
    levelView === "early" && bucketSection ? `Early EG · lvl ${bucketSection.level_range}` :
    levelView === "late"  && bucketSection ? `Late EG · lvl ${bucketSection.level_range}`  :
    undefined
  );

  useEffect(() => {
    if (!hasLife && hasEs) setGearTab("es");
  }, [hasLife, hasEs]);

  const n = buildsAnalysed(guide);
  const topGemGroups = guide.gem_link_data?.skill_gems ?? [];

  const playstyleParas = guide.playstyle_tips
    ? guide.playstyle_tips.split(/\n\n+/).filter(p => p.trim().length > 0)
    : [];

  const leagueLabel = selectedMeta?.leagueType
    ? (LEAGUE_LABELS[selectedMeta.leagueType] ?? selectedMeta.leagueType.toUpperCase())
    : null;

  return (
    <div className={styles.wrap}>

      {guide.data_pending && (
        <div className={styles.dataPending}>
          <strong>Data pending.</strong> We know this build is in the meta, but our deep
          scrape hasn&apos;t reached it yet — gem, gear and PoB sections will populate
          once analysis completes. The passive tree below is suggested by the
          recommender and is the safest part to trust right now.
        </div>
      )}

      {/* ── TOME ─────────────────────────────────────────────────────── */}
      <div className={styles.tome}>

        {/* Left page: story */}
        <div className={styles.page}>
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


          {guide.ascendancy && (
            <>
              <div className={styles.storySub} style={{ marginTop: "auto", paddingTop: "32px" }}>Ascendancy</div>
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

              {/* Trigger-chain banner: when the main skill is fired via a
                  trigger gem (Cast on Critical / Cast on Hit / etc.), the
                  user otherwise has no way to tell why both the trigger and
                  a "secondary" skill (Spark) appear in the gem list. */}
              {(guide.gem_link_data?.trigger_chains?.length ?? 0) > 0 && (
                <div style={{
                  margin: "0 0 12px",
                  padding: "10px 12px",
                  background: "linear-gradient(90deg, rgba(155,111,212,0.08) 0%, rgba(26,20,16,0) 100%)",
                  border: "1px solid rgba(155,111,212,0.3)",
                  borderLeft: "3px solid #9b6fd4",
                  fontSize: "12px",
                  color: "#c8bfa8",
                }}>
                  <span style={{
                    fontFamily: "var(--font-display)",
                    fontSize: "9px",
                    letterSpacing: "0.22em",
                    textTransform: "uppercase",
                    color: "#c4a0f0",
                    marginRight: "10px",
                  }}>Triggered Build</span>
                  <span>
                    <strong style={{ color: "#ddd" }}>{guide.skill}</strong> is fired by{" "}
                    {guide.gem_link_data!.trigger_chains!.map((c, k) => (
                      <span key={k}>
                        {k > 0 && " or "}
                        <strong style={{ color: "#c4a0f0" }}>{c.trigger_skill}</strong>
                        {" "}({c.trigger_pct.toFixed(0)}%)
                      </span>
                    ))}
                  </span>
                </div>
              )}

              {topGemGroups.map((skill, i) => (
                <div key={i} className={styles.gem}>
                  <div className={styles.gemHead}>
                    <span className={styles.gemBubble}>{skillInitial(skill.name)}</span>
                    <span className={styles.skillName}>{skill.name}</span>
                    {skill.role && skill.role !== "secondary" && (
                      <RoleBadge role={skill.role} />
                    )}
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
          <div style={{ maxWidth: "1000px", marginLeft: "auto", marginRight: "auto" }}>

            {/* Level-bucket toggle — Early EG (lvl 80-95) vs Late EG (lvl 96+).
                Frames the gear panel as an upgrade ladder: lower-level cohorts
                show what 'just-hit-maps' players have; high-level cohorts show
                fully-optimised endgame. Only renders when bucket data exists. */}
            {hasBucketToggle && (
              <div style={{
                display: "flex", gap: "4px",
                marginBottom: "20px",
                fontFamily: "var(--font-display)",
                fontSize: "11px",
                letterSpacing: "0.18em",
                textTransform: "uppercase",
              }}>
                {(["all", ...(hasEarly ? ["early" as const] : []), ...(hasLate ? ["late" as const] : [])] as const).map(view => {
                  const label =
                    view === "all"   ? "All Levels" :
                    view === "early" ? `Early EG · lvl ${guide.level_buckets?.early?.level_range ?? ""}` :
                                       `Late EG · lvl ${guide.level_buckets?.late?.level_range ?? ""}`;
                  const active = levelView === view;
                  return (
                    <button key={view} onClick={() => setLevelView(view)} style={{
                      padding: "5px 14px",
                      background: active ? "var(--amber)" : "transparent",
                      border: `1px solid ${active ? "var(--amber)" : "var(--line)"}`,
                      color: active ? "var(--bg-deep)" : "var(--text-dim)",
                      cursor: "pointer",
                      fontSize: "10px",
                      letterSpacing: "0.18em",
                    }}>
                      {label}
                    </button>
                  );
                })}
              </div>
            )}

            <GearPanel
              data={gearData}
              usefulUniques={gearUniques ?? []}
              hasLife={hasLife}
              hasEs={hasEs}
              gearTab={gearTab}
              setGearTab={setGearTab}
              bucketLabel={bucketLabel}
            />
          </div>
        </section>
      )}

      {guide.disclaimer && (
        <div className={styles.disclaimer}>{guide.disclaimer}</div>
      )}

      <div className={styles.actions}>
        <button className={styles.backButton} onClick={onReset}>← Back</button>
        {guide.pob_export && (
          <button className={styles.backButton} onClick={copyPob}>
            {pobCopied ? "Copied!" : "PoB"}
          </button>
        )}
        <button className={styles.backButton} onClick={shareGuide}>
          {shareCopied ? "Link copied!" : "Share"}
        </button>
        {session?.user && (
          <button
            className={styles.backButton}
            onClick={() => {
              setSavePanelOpen((v) => !v);
              setSaveStatus(null);
            }}
          >
            {savePanelOpen ? "Cancel" : "Save"}
          </button>
        )}
      </div>

      {savePanelOpen && session?.user && (
        <div className={styles.savePanel}>
          <input
            className={styles.saveInput}
            placeholder='Optional label — e.g. "league starter pick"'
            value={saveLabel}
            onChange={(e) => setSaveLabel(e.target.value)}
            maxLength={80}
            disabled={saving}
          />
          <button
            className={styles.backButton}
            onClick={handleSaveGuide}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save"}
          </button>
          {saveStatus === "saved" && <div className={styles.saveMsg}>Saved to <a href="/me/builds" className={styles.saveMsgLink}>your guides</a>.</div>}
          {saveStatus === "deduped" && <div className={styles.saveMsg}>Already in <a href="/me/builds" className={styles.saveMsgLink}>your guides</a>.</div>}
          {saveStatus === "error" && <div className={styles.saveError}>Save failed: {saveError}</div>}
        </div>
      )}
      {guide.pob_export && guide.pob_provenance && (
        <div className={styles.pobProvenance}>
          {guide.pob_provenance.supports_rewritten
            ? <>Based on a real lvl {guide.pob_provenance.level} player&apos;s build {guide.pob_provenance.snapshot ? `(${guide.pob_provenance.snapshot})` : ""} — gem supports rewritten to match this guide.</>
            : <>Based on a real lvl {guide.pob_provenance.level} player&apos;s build {guide.pob_provenance.snapshot ? `(${guide.pob_provenance.snapshot})` : ""}. No support changes applied.</>}
        </div>
      )}
    </div>
  );
}

// ── Role badge ────────────────────────────────────────────────────────────
// Small pill rendered next to a skill name when the role classifier tagged it
// as something other than 'secondary' — lets users see at a glance that a
// gem is an aura / trigger / utility skill rather than the main damage source.
function RoleBadge({ role }: { role: "main" | "trigger" | "aura" | "utility" | "secondary" }) {
  const palette: Record<string, { bg: string; border: string; fg: string }> = {
    main:    { bg: "rgba(232,200,74,0.10)", border: "rgba(232,200,74,0.4)",  fg: "#e8c84a" },
    trigger: { bg: "rgba(155,111,212,0.10)", border: "rgba(155,111,212,0.4)", fg: "#c4a0f0" },
    aura:    { bg: "rgba(91,163,160,0.10)",  border: "rgba(91,163,160,0.4)",  fg: "#7dd8d4" },
    utility: { bg: "rgba(160,160,160,0.10)", border: "rgba(160,160,160,0.4)", fg: "#c8bfa8" },
    secondary: { bg: "transparent", border: "transparent", fg: "transparent" },
  };
  const p = palette[role] ?? palette.secondary;
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      padding: "1px 7px",
      marginLeft: "6px",
      fontFamily: "var(--font-display)",
      fontSize: "8px",
      letterSpacing: "0.18em",
      textTransform: "uppercase",
      background: p.bg,
      border: `1px solid ${p.border}`,
      color: p.fg,
      borderRadius: "2px",
    }}>
      {role}
    </span>
  );
}
