import "@/lib/env";

import { drizzle, type PostgresJsDatabase } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import * as schema from "./schema";

type Db = PostgresJsDatabase<typeof schema>;

// Reuse one client across dev hot reloads.
const globalForDb = globalThis as unknown as { db?: Db };

export function getDb(): Db {
  if (globalForDb.db) return globalForDb.db;

  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("DATABASE_URL is not set; add it to the repo-root .env");
  }

  // prepare: false keeps us compatible with Supabase's poolers.
  const client = postgres(url, { prepare: false });
  globalForDb.db = drizzle(client, { schema });
  return globalForDb.db;
}
