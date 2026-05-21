"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { useState, useRef, useEffect } from "react";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const pathname = usePathname();
  const { data: session, status } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  // Close the user menu on outside-click
  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [menuOpen]);

  async function handleDeleteAccount() {
    setMenuOpen(false);
    const confirmed = confirm(
      "Permanently delete your account?\n\n" +
      "This will remove all your saved analyses and saved guides as well. " +
      "This cannot be undone.",
    );
    if (!confirmed) return;
    try {
      const r = await fetch("/api/me/account", { method: "DELETE" });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        alert(`Delete failed: ${e.error ?? r.statusText}`);
        return;
      }
      await signOut({ callbackUrl: "/" });
    } catch (e) {
      alert(`Delete failed: ${(e as Error).message}`);
    }
  }

  return (
    <nav className={styles.nav}>
      <Link href="/" className={styles.logo}>
        POE<span className={styles.dot}>·</span>PROFESSOR
      </Link>
      <div className={styles.links}>
        <Link href="/" className={`${styles.link} ${pathname === "/" ? styles.active : ""}`}>
          Home
        </Link>
        <Link href="/builds" className={`${styles.link} ${pathname?.startsWith("/builds") ? styles.active : ""}`}>
          Builds
        </Link>
        <Link href="/atlas" className={`${styles.link} ${pathname === "/atlas" ? styles.active : ""}`}>
          Atlas
        </Link>
        <Link href="/crafting" className={`${styles.link} ${pathname === "/crafting" ? styles.active : ""}`}>
          Crafting
        </Link>

        {/* ── Auth section ─────────────────────────────────────── */}
        {status === "loading" ? (
          <span className={styles.authLoading}>…</span>
        ) : session?.user ? (
          <div className={styles.userMenu} ref={menuRef}>
            <button
              className={styles.userBtn}
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              {session.user.image ? (
                <Image
                  src={session.user.image}
                  alt={session.user.name ?? "Avatar"}
                  width={28}
                  height={28}
                  className={styles.avatar}
                  unoptimized
                />
              ) : (
                <span className={styles.avatarFallback}>
                  {(session.user.name ?? "?").charAt(0).toUpperCase()}
                </span>
              )}
              <span className={styles.userName}>
                {session.user.name ?? "Signed in"}
              </span>
              <span className={`${styles.userCaret} ${menuOpen ? styles.userCaretOpen : ""}`} aria-hidden>▾</span>
            </button>
            {menuOpen && (
              <div className={styles.dropdown} role="menu">
                <Link
                  href="/me/builds"
                  className={styles.dropdownItem}
                  onClick={() => setMenuOpen(false)}
                >
                  My saved guides
                </Link>
                <Link
                  href="/me/analyses"
                  className={styles.dropdownItem}
                  onClick={() => setMenuOpen(false)}
                >
                  My analyses
                </Link>
                <button
                  className={styles.dropdownItem}
                  onClick={() => signOut({ callbackUrl: "/" })}
                >
                  Sign out
                </button>
                <div className={styles.dropdownSep} />
                <button
                  className={`${styles.dropdownItem} ${styles.dropdownItemDanger}`}
                  onClick={handleDeleteAccount}
                >
                  Delete account
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link href="/auth/signin" className={styles.signInBtn}>
            Sign in
          </Link>
        )}
      </div>
    </nav>
  );
}
