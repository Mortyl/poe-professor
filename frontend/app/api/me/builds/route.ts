/**
 * /api/me/builds
 *   POST  — save a build guide (skill + ascendancy combo) as a favourite
 *   GET   — list the current user's saved builds (newest first)
 *
 * Saved builds are *references*, not snapshots. When the user re-opens one,
 * we render the current live guide — so improvements to scraped data flow
 * through automatically.
 */

import { NextRequest, NextResponse } from "next/server";
import { eq, desc, and } from "drizzle-orm";
import { db } from "@/db";
import { savedBuilds } from "@/db/schema";
import { requireUserId } from "@/lib/auth-utils";

const MAX_LABEL_LENGTH = 80;

export async function POST(req: NextRequest) {
  const userIdOrErr = await requireUserId();
  if (userIdOrErr instanceof NextResponse) return userIdOrErr;
  const userId = userIdOrErr;

  let body: unknown;
  try { body = await req.json(); }
  catch { return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 }); }

  if (typeof body !== "object" || body === null) {
    return NextResponse.json({ error: "Body must be an object" }, { status: 400 });
  }
  const { skill, ascendancy, className, leagueType, label } =
    body as Record<string, unknown>;

  if (typeof skill !== "string" || !skill.trim()) {
    return NextResponse.json({ error: "skill is required" }, { status: 400 });
  }
  if (typeof ascendancy !== "string" || !ascendancy.trim()) {
    return NextResponse.json({ error: "ascendancy is required" }, { status: 400 });
  }

  const cleanLabel =
    typeof label === "string" && label.trim()
      ? label.trim().slice(0, MAX_LABEL_LENGTH)
      : null;
  const cleanClassName = typeof className === "string" ? className.trim() : null;
  const cleanLeagueType =
    typeof leagueType === "string" && ["sc", "ssf", "hc", "hcssf"].includes(leagueType)
      ? leagueType
      : "sc";

  // Soft dedupe: if this user already has this combo saved with no label
  // (or the same label), just return the existing row. Lets the same combo
  // appear multiple times only when the user is intentionally annotating
  // different variants ("LA before gear swap", "LA after gear swap").
  const existing = await db
    .select()
    .from(savedBuilds)
    .where(
      and(
        eq(savedBuilds.userId, userId),
        eq(savedBuilds.skill, skill.trim()),
        eq(savedBuilds.ascendancy, ascendancy.trim()),
      ),
    );

  const dup = existing.find((r) => (r.label ?? null) === cleanLabel);
  if (dup) {
    return NextResponse.json(
      { id: dup.id, createdAt: dup.createdAt, deduped: true },
      { status: 200 },
    );
  }

  const [inserted] = await db
    .insert(savedBuilds)
    .values({
      userId,
      skill: skill.trim(),
      ascendancy: ascendancy.trim(),
      className: cleanClassName,
      leagueType: cleanLeagueType,
      label: cleanLabel,
    })
    .returning({ id: savedBuilds.id, createdAt: savedBuilds.createdAt });

  return NextResponse.json(inserted, { status: 201 });
}

export async function GET() {
  const userIdOrErr = await requireUserId();
  if (userIdOrErr instanceof NextResponse) return userIdOrErr;
  const userId = userIdOrErr;

  const rows = await db
    .select()
    .from(savedBuilds)
    .where(eq(savedBuilds.userId, userId))
    .orderBy(desc(savedBuilds.createdAt));

  return NextResponse.json({ items: rows });
}
