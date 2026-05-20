"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import Navbar from "./components/Navbar";
import styles from "./page.module.css";

const COMPANIONS = [
  {
    id: "shaper",
    name: "The Shaper",
    role: "Generalist Scholar",
    desc: "Master of all domains. The Shaper has observed countless exiles and offers wisdom on builds, crafting, and the Atlas.",
    avatar: "/images/companions/shaper.jpg",
  },
];

interface Tool {
  href: string;
  icon: string;
  name: string;
  desc: string;
  cta: string;
}

const TOOLS: Tool[] = [
  {
    href: "/builds",
    icon: "⚔️",
    name: "Build Creator",
    desc: "Generate an AI-powered build guide. Choose class, ascendancy, weapon and skill — or let fate spin the wheel for something unexpected.",
    cta: "Create a build",
  },
  {
    href: "/atlas",
    icon: "🗺️",
    name: "Atlas Designer",
    desc: "Choose an endgame strategy and receive a guided Atlas tree with content recommendations tailored to the way you wish to farm.",
    cta: "Design strategy",
  },
  {
    href: "/crafting",
    icon: "🔨",
    name: "Crafting Architect",
    desc: "Step-by-step crafting plans for the item you desire. Bench, essence, expedition, and every method beyond — cheapest to most guaranteed.",
    cta: "Start crafting",
  },
  {
    href: "/exile",
    icon: "🧙",
    name: "Exile Refiner",
    desc: "Import your character and I will analyse your gear, passive tree and gems — then suggest exactly how to improve.",
    cta: "Refine character",
  },
];

interface Featured {
  href: string;
  tag: string;
  title: string;
  blurb: string;
}

const FEATURED: Featured[] = [
  {
    href: "/builds",
    tag: "League Starter",
    title: "Best three builds to start Fate of the Vaal",
    blurb: "Hand-picked combos that level smoothly, scale into mapping, and reach endgame on a humble purse.",
  },
  {
    href: "/builds",
    tag: "Endgame",
    title: "Builds that conquer all content",
    blurb: "Versatile setups that handle mapping, bossing, delve and the deepest corruptions of the Atlas.",
  },
  {
    href: "/builds",
    tag: "Defensive",
    title: "For those who play but one life",
    blurb: "Layered defenses against the cruelty of Wraeclast. Tanky, careful, hard to kill.",
  },
];

export default function Home() {
  const [companion, setCompanion] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("poe_companion");
    if (saved) setCompanion(saved);
    setLoaded(true);
  }, []);

  function chooseCompanion(id: string) {
    localStorage.setItem("poe_companion", id);
    window.dispatchEvent(new Event("poe_companion_selected"));
    setCompanion(id);
  }

  if (!loaded) return null;

  if (!companion) {
    return (
      <div className={styles.splash}>
        <div className={styles.splashInner}>
          <Flourish />
          <h1 className={styles.splashTitle}>Choose Your Companion</h1>
          <p className={styles.splashSub}>Your companion will guide you through the world of Wraeclast.</p>
          <div className={styles.companionGrid}>
            {COMPANIONS.map(c => (
              <button key={c.id} className={styles.companionCard} onClick={() => chooseCompanion(c.id)}>
                <div className={styles.companionAvatarWrap}>
                  <Image src={c.avatar} alt={c.name} width={120} height={120} className={styles.companionAvatar} />
                </div>
                <div className={styles.companionName}>{c.name}</div>
                <div className={styles.companionRole}>{c.role}</div>
                <div className={styles.companionDesc}>{c.desc}</div>
                <div className={styles.companionCta}>◆ Select companion →</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.container}>

          <header className={styles.hero}>
            <Flourish />
            <h1 className={styles.heroTitle}>
              POE<span className={styles.heroDot}>·</span>PROFESSOR
            </h1>
            <p className={styles.heroSubtitle}>
              An AI-bound companion for the exiles of Path of Exile 2 — real player data, expert-curated guides, and tools for every part of the game.
            </p>
          </header>

          <SectionHeader>Tools</SectionHeader>
          <div className={styles.toolGrid}>
            {TOOLS.map(t => (
              <Link key={t.href} href={t.href} className={styles.toolCard}>
                <div className={styles.toolIcon}>{t.icon}</div>
                <div className={styles.toolName}>{t.name}</div>
                <div className={styles.toolDesc}>{t.desc}</div>
                <div className={styles.toolCta}>{t.cta}</div>
              </Link>
            ))}
          </div>

          <SectionHeader>Featured this league</SectionHeader>
          <div className={styles.featuredGrid}>
            {FEATURED.map(f => (
              <Link key={f.title} href={f.href} className={styles.featuredCard}>
                <span className={styles.featuredTag}>{f.tag}</span>
                <div className={styles.featuredTitle}>{f.title}</div>
                <div className={styles.featuredBlurb}>{f.blurb}</div>
              </Link>
            ))}
          </div>

          <div className={styles.seeAll}>
            <Link href="/builds">All featured picks →</Link>
          </div>

        </div>

        <footer className={styles.footer}>
          <p>PoEProfessor is not affiliated with or endorsed by Grinding Gear Games.</p>
        </footer>
      </main>
    </>
  );
}

function Flourish() {
  return (
    <div className={styles.flourish}>
      <span className={styles.flourishLine}></span>
      <span className={styles.flourishDiamond}></span>
      <span className={`${styles.flourishDiamond} ${styles.flourishCenter}`}></span>
      <span className={styles.flourishDiamond}></span>
      <span className={styles.flourishLine}></span>
    </div>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className={styles.sectionHeader}>
      <h2 className={styles.sectionTitle}>{children}</h2>
    </div>
  );
}
