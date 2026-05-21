/**
 * Auth.js (NextAuth v5) configuration.
 *
 * Single source of truth for authentication — re-exports `auth`, `handlers`,
 * `signIn`, `signOut` for use across the app.
 *
 * Setup steps (one-time, do this BEFORE you can sign in):
 *  1. Generate a secret:   npx auth secret    (writes AUTH_SECRET to .env.local)
 *  2. Register a Discord OAuth app at https://discord.com/developers/applications
 *     - Add a redirect URI:  http://localhost:3000/api/auth/callback/discord
 *     - Copy CLIENT_ID into  AUTH_DISCORD_ID
 *     - Copy CLIENT_SECRET into AUTH_DISCORD_SECRET
 *  3. Register a Google OAuth app at https://console.cloud.google.com/apis/credentials
 *     - Application type: Web application
 *     - Authorised redirect URI: http://localhost:3000/api/auth/callback/google
 *     - Copy CLIENT_ID into  AUTH_GOOGLE_ID
 *     - Copy CLIENT_SECRET into AUTH_GOOGLE_SECRET
 *  4. Run `npm run db:push` to create the SQLite tables in users.db.
 */

import NextAuth from "next-auth";
import Discord from "next-auth/providers/discord";
import Google from "next-auth/providers/google";
import { DrizzleAdapter } from "@auth/drizzle-adapter";
import { db } from "./db";
import {
  users,
  accounts,
  sessions,
  verificationTokens,
} from "./db/schema";

export const { handlers, signIn, signOut, auth } = NextAuth({
  adapter: DrizzleAdapter(db, {
    usersTable: users,
    accountsTable: accounts,
    sessionsTable: sessions,
    verificationTokensTable: verificationTokens,
  }),
  providers: [Discord, Google],
  // Database-backed sessions (default for adapter-based setups). Lets us
  // attach saved analyses / saved builds to a real user row in the DB.
  session: { strategy: "database" },
  pages: {
    // Custom sign-in page that matches the site's tome aesthetic.
    signIn: "/auth/signin",
  },
});
