/**
 * Drizzle schema for user data (separate from the scraped poe.ninja
 * pipeline data, which lives in backend/pipeline.db).
 *
 * Tables:
 *  - `user`, `account`, `session`, `verificationToken` — Auth.js standard
 *    schema (see https://authjs.dev/getting-started/adapters/drizzle).
 *  - `savedAnalysis`, `savedBuild` — placeholders for the next features.
 *    Empty tables until the saved-state features ship.
 */

import { sqliteTable, text, integer, primaryKey } from "drizzle-orm/sqlite-core";
import type { AdapterAccountType } from "next-auth/adapters";

// ── Auth.js required tables ────────────────────────────────────────────────

export const users = sqliteTable("user", {
  id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  name: text("name"),
  email: text("email").unique(),
  emailVerified: integer("emailVerified", { mode: "timestamp_ms" }),
  image: text("image"),
  createdAt: integer("createdAt", { mode: "timestamp_ms" }).$defaultFn(() => new Date()),
});

export const accounts = sqliteTable(
  "account",
  {
    userId: text("userId")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    type: text("type").$type<AdapterAccountType>().notNull(),
    provider: text("provider").notNull(),
    providerAccountId: text("providerAccountId").notNull(),
    refresh_token: text("refresh_token"),
    access_token: text("access_token"),
    expires_at: integer("expires_at"),
    token_type: text("token_type"),
    scope: text("scope"),
    id_token: text("id_token"),
    session_state: text("session_state"),
  },
  (account) => [
    primaryKey({ columns: [account.provider, account.providerAccountId] }),
  ],
);

export const sessions = sqliteTable("session", {
  sessionToken: text("sessionToken").primaryKey(),
  userId: text("userId")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  expires: integer("expires", { mode: "timestamp_ms" }).notNull(),
});

export const verificationTokens = sqliteTable(
  "verificationToken",
  {
    identifier: text("identifier").notNull(),
    token: text("token").notNull(),
    expires: integer("expires", { mode: "timestamp_ms" }).notNull(),
  },
  (vt) => [primaryKey({ columns: [vt.identifier, vt.token] })],
);

// ── PoEProfessor user data (placeholders for next features) ────────────────

export const savedAnalyses = sqliteTable("savedAnalysis", {
  id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  userId: text("userId")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  // Snapshot of the analysis request (source, account+character or pob code, skill, etc.)
  request: text("request", { mode: "json" }).notNull(),
  // Full analyser response as captured at the time
  response: text("response", { mode: "json" }).notNull(),
  // Optional user-supplied note ("my first character", "after wand swap")
  label: text("label"),
  createdAt: integer("createdAt", { mode: "timestamp_ms" }).$defaultFn(() => new Date()),
});

export const savedBuilds = sqliteTable("savedBuild", {
  id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  userId: text("userId")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  skill: text("skill").notNull(),
  ascendancy: text("ascendancy").notNull(),
  className: text("className"),
  leagueType: text("leagueType").notNull().default("sc"),
  label: text("label"),
  createdAt: integer("createdAt", { mode: "timestamp_ms" }).$defaultFn(() => new Date()),
});
