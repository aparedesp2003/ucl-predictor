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

  // prepare: false keeps us compatible with Supabase's poolers.
  const client = postgres(databaseUrl(), { prepare: false });
  globalForDb.db = drizzle(client, { schema });
  return globalForDb.db;
}
