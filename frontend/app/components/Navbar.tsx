"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className={styles.nav}>
      <Link href="/" className={styles.logo}>
        POE<span className={styles.dot}>·</span>PROFESSOR
      </Link>
      <div className={styles.links}>
        <Link href="/" className={`${styles.link} ${pathname === "/" ? styles.active : ""}`}>
          Home
        </Link>
        <Link href="/builds" className={`${styles.link} ${pathname === "/builds" ? styles.active : ""}`}>
          Builds
        </Link>
        <Link href="/atlas" className={`${styles.link} ${pathname === "/atlas" ? styles.active : ""}`}>
          Atlas
        </Link>
        <Link href="/crafting" className={`${styles.link} ${pathname === "/crafting" ? styles.active : ""}`}>
          Crafting
        </Link>
        <Link href="/exile" className={`${styles.link} ${pathname === "/exile" ? styles.active : ""}`}>
          Refine
        </Link>
      </div>
    </nav>
  );
}
