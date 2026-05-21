/**
 * /api/me/builds/:id
 *   DELETE — remove a saved build (only the owner can delete).
 *
 * No GET endpoint — viewing a saved build redirects to the live build guide
 * at /builds/find?skill=X&ascendancy=Y, so saved builds always show fresh
 * data rather than a stale snapshot.
 */

import { NextRequest, NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { db } from "@/db";
import { savedBuilds } from "@/db/schema";
import { requireUserId } from "@/lib/auth-utils";

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const userIdOrErr = await requireUserId();
  if (userIdOrErr instanceof NextResponse) return userIdOrErr;
  const userId = userIdOrErr;
  const { id } = await params;

  const deleted = await db
    .delete(savedBuilds)
    .where(and(eq(savedBuilds.id, id), eq(savedBuilds.userId, userId)))
    .returning({ id: savedBuilds.id });

  if (deleted.length === 0) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json({ deleted: deleted[0].id });
}
