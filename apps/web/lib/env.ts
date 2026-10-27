import path from "node:path";
import { loadEnvConfig } from "@next/env";

// Secrets live in the repo-root .env (shared with apps/engine). next and drizzle-kit
// both run with apps/web as the working directory, so the root is two levels up.
export const repoRoot = path.resolve(process.cwd(), "..", "..");

loadEnvConfig(repoRoot, process.env.NODE_ENV !== "production");
