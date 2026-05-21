/**
 * SQLite + Drizzle connection.
 *
 * The database file lives at frontend/users.db (configured in drizzle.config.ts).
 * It is created automatically on first connection; `npm run db:push` writes
 * the schema into it.
 *
 * Auth.js's Drizzle adapter imports `db` from this module via the path
 * configured in auth.ts.
 */

import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import * as schema from "./schema";

const sqlite = new Database(process.env.DATABASE_PATH ?? "users.db");
// WAL mode improves concurrent read/write performance on SQLite — useful
// when Next.js dev hot-reloads multiple workers against the same file.
sqlite.pragma("journal_mode = WAL");

export const db = drizzle(sqlite, { schema });
