"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Navbar from "../../components/Navbar";
import AnalysisReport, { type BuildAnalysis } from "./AnalysisReport";
import styles from "./analyser.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Source = "pob" | "poe_ninja";

// Captured each time we run a successful analysis so we can save the
// (request, response) pair as a snapshot belonging to the user.
interface LastRequest {
  source: Source;
  pob_code?: string;
  account_name?: string;
  character_name?: string;
  main_skill?: string;
  experience_level: string;
}

export default function AnalyserPage() {
  const { data: session } = useSession();
  const router = useRouter();

  const [source, setSource] = useState<Source>("pob");
  const [pobCode, setPobCode] = useState("");
  const [accountName, setAccountName] = useState("");
  const [characterName, setCharacterName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BuildAnalysis | null>(null);
  const [lastRequest, setLastRequest] = useState<LastRequest | null>(null);

  // Save-analysis UI state
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  // Track the id of the most recently saved analysis so Share can reuse it
  // instead of creating a second DB row when the user already saved.
  const [savedAnalysisId, setSavedAnalysisId] = useState<string | null>(null);
  const [shareCopied, setShareCopied] = useState(false);

  async function runAnalysis(mainSkillOverride?: string) {
    setLoading(true);
    setError(null);
    setSaveMsg(null);
    // New analysis run → previous saved id no longer applies to this result
    setSavedAnalysisId(null);
    setShareCopied(false);
    try {
      const body: Record<string, unknown> = {
        source,
        experience_level: "league_starter",
      };
      if (source === "pob") body.pob_code = pobCode.trim();
      else { body.account_name = accountName.trim(); body.character_name = characterName.trim(); }
      if (mainSkillOverride) body.main_skill = mainSkillOverride;

      const r = await fetch(`${API_URL}/api/analyse/character`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({ detail: "Unknown error" }));
        setError(e.detail || "Failed to analyse character.");
        setResult(null);
        setLastRequest(null);
      } else {
        setResult(await r.json());
        setLastRequest(body as unknown as LastRequest);
      }
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
      setLastRequest(null);
    } finally {
      setLoading(false);
    }
  }

  // Save the current analysis (creating a DB row) and return the row id.
  // Caller decides whether to also surface a success message — used by both
  // the explicit "Save" button and the Share flow (which saves implicitly).
  async function persistAnalysis(): Promise<string | null> {
    if (!result || !lastRequest) return null;
    if (savedAnalysisId) return savedAnalysisId;   // already saved this result
    const r = await fetch(`/api/me/analyses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request: lastRequest,
        response: result,
        label: label.trim() || null,
      }),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({ error: "Unknown error" }));
      throw new Error(e.error ?? r.statusText);
    }
    const data = await r.json();
    setSavedAnalysisId(data.id);
    return data.id as string;
  }

  async function handleSave() {
    if (!result || !lastRequest) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const id = await persistAnalysis();
      if (id) {
        setSaveMsg("Saved. View it in My Analyses.");
        setLabel("");
      }
    } catch (e) {
      setSaveMsg(`Save failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  // Share saves the analysis (if not already) and copies the public share
  // URL to the clipboard. If the user isn't signed in, route to sign-in
  // first — sharing without an owner doesn't make sense.
  async function handleShare() {
    if (!result || !lastRequest) return;
    if (!session?.user) {
      router.push("/auth/signin?callbackUrl=/builds/analyser");
      return;
    }
    setSaving(true);
    setSaveMsg(null);
    try {
      const id = await persistAnalysis();
      if (!id) throw new Error("Could not save analysis");
      const url = `${window.location.origin}/share/analyses/${id}`;
      try {
        await navigator.clipboard.writeText(url);
        setShareCopied(true);
        setSaveMsg("Share link copied. Anyone with the link can view this analysis.");
        setTimeout(() => setShareCopied(false), 1800);
      } catch {
        window.prompt("Copy this share link:", url);
        setSaveMsg("Share link ready.");
      }
    } catch (e) {
      setSaveMsg(`Share failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

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
            <h1 className={styles.heroTitle}>BUILD ANALYSER</h1>
            <p className={styles.heroSubtitle}>
              Import your character, compare against hundreds of real top builds, and see exactly which supports,
              passive nodes and gear mods are falling short.
            </p>
          </header>

          {/* ── Input section ─────────────────────────────────────────── */}
          <section className={styles.inputCard}>
            <div className={styles.tabs}>
              <button
                className={`${styles.tab} ${source === "pob" ? styles.tabActive : ""}`}
                onClick={() => setSource("pob")}
              >Paste PoB code</button>
              <button
                className={`${styles.tab} ${source === "poe_ninja" ? styles.tabActive : ""}`}
                onClick={() => setSource("poe_ninja")}
              >Fetch from poe.ninja</button>
            </div>

            {source === "pob" ? (
              <div className={styles.formBody}>
                <label className={styles.fieldLabel}>Path of Building Export Code</label>
                <textarea
                  className={styles.codeBox}
                  rows={6}
                  placeholder="Paste your PoB2 export string here (in-game: Profile menu → Export Build)"
                  value={pobCode}
                  onChange={(e) => setPobCode(e.target.value)}
                />
                <div className={styles.hint}>
                  In Path of Building Community 2, click <em>Export Build</em> → <em>Copy</em>. Paste the full string.
                </div>
              </div>
            ) : (
              <div className={styles.formBody}>
                <div className={styles.row}>
                  <div className={styles.fieldGroup}>
                    <label className={styles.fieldLabel}>Account name</label>
                    <input
                      className={styles.input}
                      placeholder="e.g. YourName-1234"
                      value={accountName}
                      onChange={(e) => setAccountName(e.target.value)}
                    />
                  </div>
                  <div className={styles.fieldGroup}>
                    <label className={styles.fieldLabel}>Character name</label>
                    <input
                      className={styles.input}
                      placeholder="e.g. MyDeadeye"
                      value={characterName}
                      onChange={(e) => setCharacterName(e.target.value)}
                    />
                  </div>
                </div>
                <div className={styles.hint}>
                  Your account must be linked to <a href="https://poe.ninja/poe2" target="_blank" rel="noreferrer">poe.ninja</a> for this to work.
                  Use the poe.ninja account format (with the <code>-NNNN</code> discriminator).
                </div>
              </div>
            )}

            <button
              className={styles.runButton}
              disabled={loading || (source === "pob" ? !pobCode.trim() : (!accountName.trim() || !characterName.trim()))}
              onClick={() => runAnalysis()}
            >
              {loading ? "Analysing…" : "Analyse this character"}
            </button>

            {error && <div className={styles.error}>{error}</div>}
          </section>

          {/* ── Result section ─────────────────────────────────────────── */}
          {result && (
            <>
              <AnalysisReport
                result={result}
                onSkillChange={(newSkill) => runAnalysis(newSkill)}
              />

              {/* Save / share block — only visible when signed in */}
              <section className={styles.saveBlock}>
                {session?.user ? (
                  <>
                    <input
                      className={styles.input}
                      placeholder='Optional label — e.g. "Lightning Arrow week 1"'
                      value={label}
                      onChange={(e) => setLabel(e.target.value)}
                      maxLength={80}
                    />
                    <div className={styles.saveRow}>
                      <button
                        className={styles.runButton}
                        disabled={saving}
                        onClick={handleSave}
                      >
                        {saving && !shareCopied ? "Saving…" : (savedAnalysisId ? "Saved ✓" : "Save this analysis")}
                      </button>
                      <button
                        className={styles.runButton}
                        disabled={saving}
                        onClick={handleShare}
                      >
                        {shareCopied ? "Link copied!" : (saving ? "Saving…" : "Share analysis")}
                      </button>
                    </div>
                    {saveMsg && <div className={styles.saveMsg}>{saveMsg}</div>}
                  </>
                ) : (
                  <div className={styles.saveSignedOut}>
                    <button
                      className={styles.runButton}
                      onClick={() => router.push("/auth/signin?callbackUrl=/builds/analyser")}
                    >
                      Sign in to save or share this analysis
                    </button>
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </main>
    </>
  );
}
