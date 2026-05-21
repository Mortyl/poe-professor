"use client";

import styles from "./analyser.module.css";

// ── Types (shared between the live analyser and the saved-analysis viewer) ──

export interface GemFinding { kind: string; support: string; meta_pct: number; severity: string; }
export interface GemAnalysis {
  main_skill: string;
  builds_analysed: number;
  confidence: number;
  user_supports: string[];
  findings: GemFinding[];
  available: boolean;
  message: string;
}
export interface PassiveFinding { kind: string; node_id: number; node_name: string; meta_pct: number; severity: string; }
export interface PassiveAnalysis {
  builds_analysed: number;
  confidence: number;
  user_node_count: number;
  findings: PassiveFinding[];
  available: boolean;
  message: string;
}
export interface GearFinding { slot: string; kind: string; message: string; severity: string; }
export interface GearAnalysis {
  total_uncapped_res: Record<string, number>;
  findings: GearFinding[];
  available: boolean;
  message: string;
}
export interface BuildAnalysis {
  skill: string;
  ascendancy: string;
  class_name: string;
  level: number;
  experience_level: string;
  candidate_skills: string[];
  gem: GemAnalysis;
  passive: PassiveAnalysis;
  gear: GearAnalysis;
}

// ── Report component ─────────────────────────────────────────────────────

interface Props {
  result: BuildAnalysis;
  // Optional: when provided, the skill picker is interactive and calls this
  // on change. Omit on the saved-analysis viewer where the result is frozen.
  onSkillChange?: (newSkill: string) => void;
}

export default function AnalysisReport({ result, onSkillChange }: Props) {
  return (
    <section className={styles.resultSection}>
      <header className={styles.resultHeader}>
        <div className={styles.resultMeta}>
          <span className={styles.resultLabel}>Detected</span>
          <h2 className={styles.resultTitle}>{result.skill || "(no main skill found)"}</h2>
          <p className={styles.resultSub}>
            {[result.class_name, result.ascendancy, result.level ? `Level ${result.level}` : null]
              .filter(Boolean).join(" · ")}
          </p>
        </div>
        {onSkillChange && result.candidate_skills.length > 1 && (
          <div className={styles.skillPicker}>
            <label className={styles.fieldLabel}>Analyse a different skill:</label>
            <select
              className={styles.select}
              value={result.skill}
              onChange={(e) => onSkillChange(e.target.value)}
            >
              {result.candidate_skills.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        )}
      </header>

      <div className={styles.axisGrid}>
        {/* ── Gems ─────────────────────────────────────────────── */}
        <Axis
          title="Gem Links"
          confidence={result.gem.confidence}
          buildsAnalysed={result.gem.builds_analysed}
          available={result.gem.available}
          message={result.gem.message}
          emptyMessage="Your gem links match the meta. Nothing to flag."
          findings={result.gem.findings.map((f) => ({
            severity: f.severity,
            title: f.kind === "missing_high_value"
              ? `Missing: ${f.support}`
              : `Unusual: ${f.support}`,
            body: f.kind === "missing_high_value"
              ? `${f.meta_pct.toFixed(0)}% of top builds use this support. You don't have it socketed.`
              : `${f.meta_pct.toFixed(0)}% of top builds use this — either a niche pick or replace with a more common one.`,
          }))}
        />

        {/* ── Passives ─────────────────────────────────────────── */}
        <Axis
          title="Passive Tree"
          confidence={result.passive.confidence}
          buildsAnalysed={result.passive.builds_analysed}
          available={result.passive.available}
          message={result.passive.message}
          emptyMessage="Your tree allocations match the meta closely."
          subtitle={`You have ${result.passive.user_node_count} nodes allocated.`}
          findings={result.passive.findings.slice(0, 12).map((f) => ({
            severity: f.severity,
            title: f.kind === "missing_core"
              ? `Missing notable: ${f.node_name}`
              : `Unusual pick: ${f.node_name}`,
            body: f.kind === "missing_core"
              ? `${f.meta_pct.toFixed(0)}% of top builds take this notable.`
              : `Only ${f.meta_pct.toFixed(0)}% of top builds take this — consider refunding for a higher-impact node.`,
          }))}
          truncated={result.passive.findings.length > 12 ? result.passive.findings.length - 12 : 0}
        />

        {/* ── Gear ─────────────────────────────────────────────── */}
        <Axis
          title="Gear"
          confidence={1}
          buildsAnalysed={0}
          available={result.gear.available}
          message={result.gear.message}
          emptyMessage="Every slot is pulling its weight."
          subtitle={`Gear-only resistance: Fire ${result.gear.total_uncapped_res.fire ?? 0}% · Cold ${result.gear.total_uncapped_res.cold ?? 0}% · Lightning ${result.gear.total_uncapped_res.lightning ?? 0}%`}
          findings={result.gear.findings.map((f) => ({
            severity: f.severity,
            title: f.slot,
            body: f.message,
          }))}
          hideConfidence
        />
      </div>

      <div className={styles.disclaimer}>
        Compared against {Math.max(result.gem.builds_analysed, result.passive.builds_analysed)} real top builds of {result.skill} / {result.ascendancy}.
        Findings are guidance — your build, your call.
      </div>
    </section>
  );
}

// ── Axis subcomponent ────────────────────────────────────────────────────

interface AxisFinding { severity: string; title: string; body: string; }
interface AxisProps {
  title: string;
  confidence: number;
  buildsAnalysed: number;
  available: boolean;
  message: string;
  findings: AxisFinding[];
  emptyMessage: string;
  subtitle?: string;
  truncated?: number;
  hideConfidence?: boolean;
}

function Axis({ title, confidence, buildsAnalysed, available, message, findings, emptyMessage, subtitle, truncated, hideConfidence }: AxisProps) {
  const lowConfidence = !hideConfidence && available && confidence < 1.0;
  return (
    <div className={styles.axis}>
      <header className={styles.axisHead}>
        <h3 className={styles.axisTitle}>{title}</h3>
        {!hideConfidence && available && (
          <span className={styles.axisN}>n = {buildsAnalysed.toLocaleString()}</span>
        )}
      </header>
      {subtitle && <div className={styles.axisSubtitle}>{subtitle}</div>}
      {lowConfidence && (
        <div className={styles.lowConfidence}>
          Low-confidence ({Math.round(confidence * 100)}%) — fewer than 50 builds analysed for this combo.
        </div>
      )}
      {!available ? (
        <div className={styles.noData}>{message}</div>
      ) : findings.length === 0 ? (
        <div className={styles.allGood}>✓ {emptyMessage}</div>
      ) : (
        <ul className={styles.findingList}>
          {findings.map((f, i) => (
            <li key={i} className={`${styles.finding} ${styles[`severity_${f.severity}`]}`}>
              <div className={styles.findingTitle}>{f.title}</div>
              <div className={styles.findingBody}>{f.body}</div>
            </li>
          ))}
        </ul>
      )}
      {truncated ? (
        <div className={styles.truncated}>+ {truncated} more lower-priority findings hidden.</div>
      ) : null}
    </div>
  );
}
