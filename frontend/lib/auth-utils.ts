/**
 * Small server-side helper for protected route handlers.
 *
 * Usage:
 *   const userId = await requireUserId();
 *   if (userId instanceof NextResponse) return userId;  // 401 returned
 *   // ...userId is a string here
 */

import { NextResponse } from "next/server";
import { auth } from "@/auth";

export async function requireUserId(): Promise<string | NextResponse> {
  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }
  return userId;
}
