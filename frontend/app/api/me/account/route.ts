/**
 * /api/me/account
 *   DELETE — permanently remove the current user's account.
 *
 * The user row deletion cascades (via ON DELETE CASCADE on the FK
 * references in db/schema.ts) to:
 *   - account     (OAuth provider linkings)
 *   - session     (active sessions — effectively logs them out)
 *   - savedAnalysis
 *   - savedBuild
 *
 * After this call succeeds the client should call signOut() to clear
 * the local session cookie.
 */

import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db } from "@/db";
import { users } from "@/db/schema";
import { requireUserId } from "@/lib/auth-utils";

export async function DELETE() {
  const userIdOrErr = await requireUserId();
  if (userIdOrErr instanceof NextResponse) return userIdOrErr;
  const userId = userIdOrErr;

  const deleted = await db
    .delete(users)
    .where(eq(users.id, userId))
    .returning({ id: users.id });

  if (deleted.length === 0) {
    return NextResponse.json({ error: "User not found" }, { status: 404 });
  }
  return NextResponse.json({ deleted: deleted[0].id });
}
