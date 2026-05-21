"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Navbar from "../../components/Navbar";
import styles from "./builds.module.css";

interface SavedBuild {
  id: string;
  skill: string;
  ascendancy: string;
  className: string | null;
  leagueType: string;
  label: string | null;
  createdAt: string;
}

export default function MySavedBuildsPage() {
  const { status } = useSession();
  const router = useRouter();
  const [items, setItems] = useState<SavedBuild[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/auth/signin?callbackUrl=/me/builds");
    }
  }, [status, router]);

  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/me/builds");
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
    if (!confirm("Remove this build from your saved guides?")) return;
    try {
      const r = await fetch(`/api/me/builds/${id}`, { method: "DELETE" });
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
            <h1 className={styles.heroTitle}>MY SAVED GUIDES</h1>
            <p className={styles.heroSubtitle}>
              Build guides you&apos;ve favourited. Click one to view the latest version —
              guides update as more data is scraped, so saved entries stay current automatically.
            </p>
          </header>

          {status === "loading" && <div className={styles.loading}>Loading…</div>}
          {error && <div className={styles.error}>{error}</div>}

          {items && items.length === 0 && (
            <div className={styles.empty}>
              No saved guides yet.{" "}
              <Link href="/builds/find" className={styles.link}>Find a build</Link>,
              generate a guide, and click <em>★ Save Guide</em> to keep it here.
            </div>
          )}

          {items && items.length > 0 && (
            <ul className={styles.list}>
              {items.map((it) => {
                const href = `/builds/find?skill=${encodeURIComponent(it.skill)}&ascendancy=${encodeURIComponent(it.ascendancy)}`;
                return (
                  <li key={it.id} className={styles.item}>
                    <Link href={href} className={styles.itemLink}>
                      <div className={styles.itemPrimary}>
                        <span className={styles.itemSkill}>{it.skill}</span>
                        <span className={styles.itemAsc}>{it.ascendancy}</span>
                      </div>
                      <div className={styles.itemSecondary}>
                        {it.label && <span className={styles.itemLabel}>{it.label}</span>}
                        {it.className && <span className={styles.itemMeta}>{it.className}</span>}
                        <span className={styles.itemMeta}>{it.leagueType.toUpperCase()}</span>
                        <span className={styles.itemDate}>{new Date(it.createdAt).toLocaleDateString()}</span>
                      </div>
                    </Link>
                    <button
                      className={styles.deleteBtn}
                      onClick={() => handleDelete(it.id)}
                      aria-label="Remove this saved guide"
                      title="Remove"
                    >×</button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </main>
    </>
  );
}
