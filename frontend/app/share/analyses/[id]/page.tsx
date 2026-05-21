/**
 * Public shared-analysis view.
 *
 * No auth required — accessed by URL only. Renders the same AnalysisReport
 * component the signed-in user sees, plus a "Analyse your own character"
 * CTA at the top targeted at non-authed viewers (this is the conversion
 * surface for shared links).
 */

import Link from "next/link";
import { notFound } from "next/navigation";
import { eq } from "drizzle-orm";
import type { Metadata } from "next";
import Navbar from "../../../components/Navbar";
import AnalysisReport, {
  type BuildAnalysis,
} from "../../../builds/analyser/AnalysisReport";
import { db } from "@/db";
import { savedAnalyses } from "@/db/schema";
import styles from "./share.module.css";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function loadShared(id: string) {
  if (!UUID_RE.test(id)) return null;
  const [row] = await db
    .select({
      id: savedAnalyses.id,
      label: savedAnalyses.label,
      createdAt: savedAnalyses.createdAt,
      response: savedAnalyses.response,
    })
    .from(savedAnalyses)
    .where(eq(savedAnalyses.id, id))
    .limit(1);
  return row ?? null;
}

// ── Open Graph metadata — controls how the URL renders in Discord/etc ──
export async function generateMetadata(
  { params }: { params: Promise<{ id: string }> },
): Promise<Metadata> {
  const { id } = await params;
  const row = await loadShared(id);
  if (!row) return { title: "Shared build analysis · PoEProfessor" };

  const r = row.response as BuildAnalysis;
  const titleSkill = r?.skill || "Build";
  const titleAsc = r?.ascendancy ? ` ${r.ascendancy}` : "";
  const gemFindings = r?.gem?.findings?.length ?? 0;
  const gearFindings = r?.gear?.findings?.length ?? 0;

  return {
    title: `${titleSkill}${titleAsc} analysis · PoEProfessor`,
    description: row.label
      ? `${row.label} — ${gemFindings} gem findings, ${gearFindings} gear findings.`
      : `${gemFindings} gem findings, ${gearFindings} gear findings.`,
    openGraph: {
      title: `${titleSkill}${titleAsc} — Build Analysis`,
      description: row.label ?? "Compared against real top builds on PoEProfessor.",
      type: "article",
    },
  };
}

export default async function SharedAnalysisPage(
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const row = await loadShared(id);
  if (!row) notFound();

  const result = row.response as BuildAnalysis;

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.container}>
          <div className={styles.cta}>
            <div className={styles.ctaLeft}>
              <div className={styles.ctaEyebrow}>Shared analysis</div>
              <div className={styles.ctaTitle}>Want to see how your build stacks up?</div>
            </div>
            <Link href="/builds/analyser" className={styles.ctaButton}>
              Analyse your character →
            </Link>
          </div>

          <header className={styles.savedHeader}>
            {row.label && <h1 className={styles.savedLabel}>{row.label}</h1>}
            <div className={styles.savedDate}>
              Shared analysis · {new Date(row.createdAt as unknown as string).toLocaleDateString()}
            </div>
          </header>

          <AnalysisReport result={result} />
        </div>
      </main>
    </>
  );
}
