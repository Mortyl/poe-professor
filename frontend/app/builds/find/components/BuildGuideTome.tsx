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
  const gearData    = gearTab === "life" ? guide.gear_data_life : guide.gear_data_es;
  const gearUniques = gearTab === "life" ? guide.useful_uniques : guide.useful_uniques_es;

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
            <GearPanel
              data={gearData}
              usefulUniques={gearUniques ?? []}
              hasLife={hasLife}
              hasEs={hasEs}
              gearTab={gearTab}
              setGearTab={setGearTab}
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
