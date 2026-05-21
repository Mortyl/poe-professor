"use client";

import Link from "next/link";
import Navbar from "../components/Navbar";
import styles from "./page.module.css";

interface Section {
  href: string;
  icon: string;
  name: string;
  desc: string;
  cta: string;
}

const SECTIONS: Section[] = [
  {
    href: "/builds/find",
    icon: "🔍",
    name: "Find",
    desc: "Browse builds by archetype or generate a full guide for any class, ascendancy and skill — all backed by real top-player data.",
    cta: "Find a build",
  },
  {
    href: "/builds/tier-list",
    icon: "📜",
    name: "Tier list",
    desc: "See which builds dominate the current league. Data from real player counts and endgame retention, plus a community vote.",
    cta: "View tier list",
  },
  {
    href: "/builds/analyser",
    icon: "🧙",
    name: "Analyser",
    desc: "Import your character and we'll compare your gear, gems and passives against the top builds — then surface exactly what to change.",
    cta: "Analyse a build",
  },
];

export default function BuildsLandingPage() {
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
            <h1 className={styles.heroTitle}>BUILDS</h1>
            <p className={styles.heroSubtitle}>
              Three ways to make your next character better — find a build, see what&apos;s strong this league,
              or hand us your character for specific advice.
            </p>
          </header>

          <div className={styles.sectionGrid}>
            {SECTIONS.map((s) => (
              <Link key={s.href} href={s.href} className={styles.sectionCard}>
                <div className={styles.sectionIcon}>{s.icon}</div>
                <div className={styles.sectionName}>{s.name}</div>
                <div className={styles.sectionDesc}>{s.desc}</div>
                <div className={styles.sectionCta}>{s.cta} →</div>
              </Link>
            ))}
          </div>
        </div>
      </main>
    </>
  );
}
