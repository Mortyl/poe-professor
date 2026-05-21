/**
 * /api/me/analyses
 *   POST  — save a new analysis snapshot for the current user
 *   GET   — list the current user's saved analyses (newest first)
 */

import { NextRequest, NextResponse } from "next/server";
import { eq, desc } from "drizzle-orm";
import { db } from "@/db";
import { savedAnalyses } from "@/db/schema";
import { requireUserId } from "@/lib/auth-utils";

const MAX_LABEL_LENGTH = 80;
const MAX_RESPONSE_BYTES = 256 * 1024; // 256 KB — analysis responses are ~5–10 KB; this is a sanity check.

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
  const { request, response, label } = body as Record<string, unknown>;

  if (typeof request !== "object" || request === null) {
    return NextResponse.json({ error: "Missing 'request' field" }, { status: 400 });
  }
  if (typeof response !== "object" || response === null) {
    return NextResponse.json({ error: "Missing 'response' field" }, { status: 400 });
  }

  // Size guard — we don't want a 50MB blob in users.db
  const responseSize = JSON.stringify(response).length;
  if (responseSize > MAX_RESPONSE_BYTES) {
    return NextResponse.json({ error: "Response too large" }, { status: 413 });
  }

  const cleanLabel =
    typeof label === "string" && label.trim()
      ? label.trim().slice(0, MAX_LABEL_LENGTH)
      : null;

  const [inserted] = await db
    .insert(savedAnalyses)
    .values({
      userId,
      // Drizzle's `mode: "json"` text columns serialise automatically
      request: request as object,
      response: response as object,
      label: cleanLabel,
    })
    .returning({ id: savedAnalyses.id, createdAt: savedAnalyses.createdAt });

  return NextResponse.json(inserted, { status: 201 });
}

export async function GET() {
  const userIdOrErr = await requireUserId();
  if (userIdOrErr instanceof NextResponse) return userIdOrErr;
  const userId = userIdOrErr;

  const rows = await db
    .select()
    .from(savedAnalyses)
    .where(eq(savedAnalyses.userId, userId))
    .orderBy(desc(savedAnalyses.createdAt));

  // Project to a list-view shape — pull skill/ascendancy/level out of the
  // stored response so the listing page doesn't have to parse blobs twice.
  const items = rows.map((r) => {
    const resp = (r.response as Record<string, unknown>) ?? {};
    return {
      id: r.id,
      label: r.label,
      createdAt: r.createdAt,
      skill: (resp.skill as string) ?? "",
      ascendancy: (resp.ascendancy as string) ?? "",
      level: (resp.level as number) ?? 0,
    };
  });

  return NextResponse.json({ items });
}
