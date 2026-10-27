import "./lib/env";

import { defineConfig } from "drizzle-kit";

// apps/engine owns the schema via Alembic. Use drizzle-kit only for `pull`/`studio`,
// never `push`/`migrate`.
export default defineConfig({
  dialect: "postgresql",
  schema: "./lib/db/schema.ts",
  out: "./drizzle",
  dbCredentials: { url: process.env.DATABASE_URL ?? "" },
});
