/**
 * /api/me/analyses/:id
 *   GET     — fetch the full saved analysis (request + response payloads)
 *   DELETE  — remove this analysis (only the owner can delete)
 *
 * All scoped to the current user — a request with a valid id that belongs
 * to a different user returns 404 (we don't leak existence of others' rows).
 */

import { NextRequest, NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { db } from "@/db";
import { savedAnalyses } from "@/db/schema";
import { requireUserId } from "@/lib/auth-utils";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const userIdOrErr = await requireUserId();
  if (userIdOrErr instanceof NextResponse) return userIdOrErr;
  const userId = userIdOrErr;
  const { id } = await params;

  const [row] = await db
    .select()
    .from(savedAnalyses)
    .where(and(eq(savedAnalyses.id, id), eq(savedAnalyses.userId, userId)))
    .limit(1);

  if (!row) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json(row);
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const userIdOrErr = await requireUserId();
  if (userIdOrErr instanceof NextResponse) return userIdOrErr;
  const userId = userIdOrErr;
  const { id } = await params;

  const deleted = await db
    .delete(savedAnalyses)
    .where(and(eq(savedAnalyses.id, id), eq(savedAnalyses.userId, userId)))
    .returning({ id: savedAnalyses.id });

  if (deleted.length === 0) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json({ deleted: deleted[0].id });
}
