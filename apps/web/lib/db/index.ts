import "@/lib/env";

import { drizzle, type PostgresJsDatabase } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import * as schema from "./schema";

type Db = PostgresJsDatabase<typeof schema>;

// Reuse one client across dev hot reloads.
const globalForDb = globalThis as unknown as { db?: Db };

// The web reads through the web_readonly role (docs/sql/web_readonly.sql). In development only,
// fall back to the engine's DATABASE_URL so a fresh checkout still renders.
function databaseUrl(): string {
  const url = process.env.WEB_DATABASE_URL;
  if (url) return url;
  if (process.env.NODE_ENV !== "production" && process.env.DATABASE_URL) {
    console.warn(
      "WEB_DATABASE_URL is not set; falling back to DATABASE_URL (development only)",
    );
    return process.env.DATABASE_URL;
  }
  throw new Error("WEB_DATABASE_URL is not set; add it to the repo-root .env");
}

export function getDb(): Db {
  if (globalForDb.db) return globalForDb.db;

  // Production runs on serverless functions against Supabase's transaction pooler (port 6543):
  // prepared statements do not survive it (prepare: false), and every warm instance holds its own
  // pool, so keep each one small and let idle connections go. See README "Database connections".
  const production = process.env.NODE_ENV === "production";
  const client = postgres(databaseUrl(), {
    prepare: false,
    max: production ? 3 : 10,
    idle_timeout: 20,
    connect_timeout: 10,
  });
  globalForDb.db = drizzle(client, { schema });
  return globalForDb.db;
}
