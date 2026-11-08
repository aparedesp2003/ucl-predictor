import "server-only";

import { eq } from "drizzle-orm";
import { cacheLife, cacheTag } from "next/cache";

import { getDb } from "@/lib/db";
import { webModelScoreboard as v } from "@/lib/db/schema";

import type { CacheTag } from "./tags";
import type { ScoreRow } from "./types";

/** Live (pre-kick-off) prediction scores per model for one season; empty until a match is scored. */
export async function getScoreboard(season: string): Promise<ScoreRow[]> {
  "use cache";
  cacheTag("scoreboard" satisfies CacheTag);
  cacheLife("hours");

  const rows = await getDb().select().from(v).where(eq(v.season, season));
  return rows.map((r) => ({
    model: r.model,
    season: r.season,
    n: r.n,
    logLoss: r.logLoss,
    rps: r.rps,
    accuracy: r.accuracy,
    uniformLogLoss: r.uniformLogLoss,
    uniformRps: r.uniformRps,
    uniformAccuracy: r.uniformAccuracy,
    isPrimary: r.isPrimary,
  }));
}
