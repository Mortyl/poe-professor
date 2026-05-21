/**
 * /api/share/analyses/:id
 *   GET — fetch a saved analysis WITHOUT auth check.
 *
 * The `id` is a 128-bit random UUID (crypto.randomUUID()), so it acts as
 * its own share token: anyone who has the URL can view, no one can guess
 * a valid id. Same security model as Google Docs "anyone with the link".
 *
 * The user's *list* of analyses stays auth-gated at /api/me/analyses —
 * only specific analyses whose URLs are actively shared become reachable.
 */

import { NextRequest, NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db } from "@/db";
import { savedAnalyses } from "@/db/schema";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // Basic shape guard — reject malformed input fast without hitting the DB
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

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

  if (!row) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  // Note: we deliberately don't return the `request` field publicly.
  // The shared view shows the analysis, not the input (e.g. account
  // name from a poe.ninja-fetched analysis).
  return NextResponse.json(row);
}
