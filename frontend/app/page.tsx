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
          <p className={styles.eyebrow}>Path of Exile 2 · Companion Tool</p>
          <h1 className={styles.splashTitle}>Choose Your Companion</h1>
          <p className={styles.splashSub}>
            Your companion will guide you through the world of Wraeclast.
          </p>
          <div className={styles.companionGrid}>
            {COMPANIONS.map(c => (
              <button key={c.id} className={styles.companionCard} onClick={() => chooseCompanion(c.id)}>
                <div className={styles.companionAvatarWrap}>
                  <Image src={c.avatar} alt={c.name} width={120} height={120} className={styles.companionAvatar} />
                </div>
                <div className={styles.companionName}>{c.name}</div>
                <div className={styles.companionRole}>{c.role}</div>
                <div className={styles.companionDesc}>{c.desc}</div>
                <div className={styles.companionCta}>Select Companion →</div>
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
        <section className={styles.hero}>
          <div className={styles.heroInner}>
            <p className={styles.eyebrow}>Path of Exile 2 · Companion Tool</p>
            <h1 className={styles.heroTitle}>
              Welcome to <span>PoEProfessor</span>
            </h1>
            <p className={styles.heroSub}>What troubles you today, Exile?</p>
          </div>
        </section>

        <section className={styles.cards}>
          <div className={styles.cardRow}>
            <Link href="/builds" className={`${styles.card} ${styles.cardGold}`}>
              <div className={styles.cardIcon}>⚔️</div>
              <h2 className={styles.cardTitle}>Build Creator</h2>
              <p className={styles.cardDesc}>
                Generate an AI-powered build guide. Choose your class, ascendancy, weapon and skill — or spin the wheel for something unexpected.
              </p>
              <span className={styles.cardCta}>Create a Build →</span>
            </Link>

            <Link href="/atlas" className={`${styles.card} ${styles.cardBlue}`}>
              <div className={styles.cardIcon}>🗺️</div>
              <h2 className={styles.cardTitle}>Atlas Designer</h2>
              <p className={styles.cardDesc}>
                Tell me what you want to farm — currency, equipment, bosses — and I will generate the optimal atlas passive strategy to get you there.
              </p>
              <span className={styles.cardCta}>Design Strategy →</span>
            </Link>
          </div>

          <div className={styles.cardRow}>
            <Link href="/crafting" className={`${styles.card} ${styles.cardGreen}`}>
              <div className={styles.cardIcon}>🔨</div>
              <h2 className={styles.cardTitle}>Crafting Architect</h2>
              <p className={styles.cardDesc}>
                Paste an item and describe your target mod. I will outline the best crafting methods from cheapest to most guaranteed.
              </p>
              <span className={styles.cardCta}>Start Crafting →</span>
            </Link>

            <Link href="/exile" className={`${styles.card} ${styles.cardPurple}`}>
              <div className={styles.cardIcon}>🧙</div>
              <h2 className={styles.cardTitle}>Exile Refiner</h2>
              <p className={styles.cardDesc}>
                Import your character and I will analyse your gear, passive tree and gems — then suggest exactly how to improve.
              </p>
              <span className={styles.cardCta}>Refine Character →</span>
            </Link>
          </div>
        </section>

        <footer className={styles.footer}>
          <p>PoEProfessor is not affiliated with or endorsed by Grinding Gear Games.</p>
        </footer>
      </main>
    </>
  );
}
