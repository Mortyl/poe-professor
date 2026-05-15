"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className={styles.nav}>
      <Link href="/" className={styles.logo}>
        <div className={styles.gem} />
        PoEProfessor
      </Link>
      <div className={styles.links}>
        <Link href="/builds" className={`${styles.link} ${pathname === "/builds" ? styles.active : ""}`}>
          Build Creator
        </Link>
        <Link href="/atlas" className={`${styles.link} ${pathname === "/atlas" ? styles.active : ""}`}>
          Atlas Designer
        </Link>
        <Link href="/crafting" className={`${styles.link} ${pathname === "/crafting" ? styles.active : ""}`}>
          Crafting Architect
        </Link>
        <Link href="/exile" className={`${styles.link} ${pathname === "/exile" ? styles.active : ""}`}>
          Exile Refiner
        </Link>
      </div>
    </nav>
  );
}
