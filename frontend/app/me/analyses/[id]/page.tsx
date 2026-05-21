"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Navbar from "../../../components/Navbar";
import AnalysisReport, { type BuildAnalysis } from "../../../builds/analyser/AnalysisReport";
import styles from "./detail.module.css";

function buildShareUrl(id: string): string {
  if (typeof window === "undefined") return `/share/analyses/${id}`;
  return `${window.location.origin}/share/analyses/${id}`;
}

interface SavedRow {
  id: string;
  label: string | null;
  createdAt: string;
  request: unknown;
  response: BuildAnalysis;
}

export default function SavedAnalysisDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);  // Next.js 16 — params is a Promise in Client Components
  const { status } = useSession();
  const router = useRouter();
  const [row, setRow] = useState<SavedRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push(`/auth/signin?callbackUrl=/me/analyses/${id}`);
    }
  }, [status, router, id]);

  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/api/me/analyses/${id}`);
        if (r.status === 404) throw new Error("This analysis doesn't exist or isn't yours.");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (!cancelled) setRow(json);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, [status, id]);

  async function handleDelete() {
    if (!confirm("Delete this analysis? This can't be undone.")) return;
    try {
      const r = await fetch(`/api/me/analyses/${id}`, { method: "DELETE" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      router.push("/me/analyses");
    } catch (e) {
      alert(`Delete failed: ${(e as Error).message}`);
    }
  }

  const [shareCopied, setShareCopied] = useState(false);

  async function handleShare() {
    const url = buildShareUrl(id);
    try {
      await navigator.clipboard.writeText(url);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 1800);
    } catch {
      // Older browsers / non-secure contexts may block clipboard — fall back
      // to selecting the URL in a prompt the user can copy manually.
      window.prompt("Copy this share link:", url);
    }
  }

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.container}>
          <div className={styles.crumb}>
            <Link href="/me/analyses" className={styles.crumbLink}>← My Analyses</Link>
            {row && (
              <div className={styles.crumbActions}>
                <button onClick={handleShare} className={styles.shareBtn}>
                  {shareCopied ? "Link copied!" : "Share"}
                </button>
                <button onClick={handleDelete} className={styles.deleteBtn}>Delete</button>
              </div>
            )}
          </div>

          {error && <div className={styles.error}>{error}</div>}
          {!row && !error && <div className={styles.loading}>Loading…</div>}

          {row && (
            <>
              <header className={styles.savedHeader}>
                {row.label && <h1 className={styles.savedLabel}>{row.label}</h1>}
                <div className={styles.savedDate}>
                  Saved {new Date(row.createdAt).toLocaleString()}
                </div>
              </header>
              <AnalysisReport result={row.response} />
            </>
          )}
        </div>
      </main>
    </>
  );
}
