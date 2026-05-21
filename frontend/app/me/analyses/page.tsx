"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Navbar from "../../components/Navbar";
import styles from "./analyses.module.css";

interface ListItem {
  id: string;
  label: string | null;
  createdAt: string;            // ISO from JSON serialisation
  skill: string;
  ascendancy: string;
  level: number;
}

export default function MyAnalysesPage() {
  const { status } = useSession();
  const router = useRouter();
  const [items, setItems] = useState<ListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Redirect signed-out users to sign-in (with callback back to this page)
  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/auth/signin?callbackUrl=/me/analyses");
    }
  }, [status, router]);

  // Load list once we know we're authenticated
  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/me/analyses");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (!cancelled) setItems(json.items);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, [status]);

  async function handleDelete(id: string) {
    if (!confirm("Delete this analysis? This can't be undone.")) return;
    try {
      const r = await fetch(`/api/me/analyses/${id}`, { method: "DELETE" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setItems((prev) => prev?.filter((it) => it.id !== id) ?? null);
    } catch (e) {
      alert(`Delete failed: ${(e as Error).message}`);
    }
  }

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.container}>
          <header className={styles.hero}>
            <h1 className={styles.heroTitle}>MY ANALYSES</h1>
            <p className={styles.heroSubtitle}>
              Snapshots of your character analyses. Click one to view the full report.
            </p>
          </header>

          {status === "loading" && <div className={styles.loading}>Loading…</div>}
          {error && <div className={styles.error}>{error}</div>}

          {items && items.length === 0 && (
            <div className={styles.empty}>
              No saved analyses yet.{" "}
              <Link href="/builds/analyser" className={styles.link}>Run an analysis</Link>{" "}
              and click <em>Save this analysis</em> to keep it here.
            </div>
          )}

          {items && items.length > 0 && (
            <ul className={styles.list}>
              {items.map((it) => (
                <li key={it.id} className={styles.item}>
                  <Link href={`/me/analyses/${it.id}`} className={styles.itemLink}>
                    <div className={styles.itemPrimary}>
                      <span className={styles.itemSkill}>{it.skill || "(unknown skill)"}</span>
                      <span className={styles.itemAsc}>{it.ascendancy}</span>
                    </div>
                    <div className={styles.itemSecondary}>
                      {it.label && <span className={styles.itemLabel}>{it.label}</span>}
                      {it.level > 0 && <span className={styles.itemLevel}>Level {it.level}</span>}
                      <span className={styles.itemDate}>{new Date(it.createdAt).toLocaleDateString()}</span>
                    </div>
                  </Link>
                  <button
                    className={styles.deleteBtn}
                    onClick={() => handleDelete(it.id)}
                    aria-label="Delete this analysis"
                    title="Delete"
                  >×</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </>
  );
}
