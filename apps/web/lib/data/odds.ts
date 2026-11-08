import "server-only";

import { desc } from "drizzle-orm";
import { cacheLife, cacheTag } from "next/cache";

import { getDb } from "@/lib/db";
import { webTitleOdds as v } from "@/lib/db/schema";

import type { CacheTag } from "./tags";
import type { TitleRace } from "./types";

/** Title odds from the latest simulation of the current season, or null before the first run. */
export async function getTitleRace(): Promise<TitleRace | null> {
  "use cache";
  cacheTag("odds" satisfies CacheTag);
  cacheLife("hours");

  const rows = await getDb()
    .select()
    .from(v)
    .orderBy(desc(v.pWin), desc(v.pFinal));
  const first = rows[0];
  if (!first) return null;

  return {
    season: first.season,
    nSims: first.nSims,
    runCreatedAt: first.runCreatedAt.toISOString(),
    resultsThrough: first.resultsThrough,
    teams: rows.map((r) => ({
      team: { id: r.teamId, name: r.name, shortName: r.shortName, tla: r.tla },
      pTop8: r.pTop8,
      pPlayoff: r.pPlayoff,
      pOut: r.pOut,
      pR16: r.pR16,
      pQf: r.pQf,
      pSf: r.pSf,
      pFinal: r.pFinal,
      pWin: r.pWin,
      expectedPoints: r.expectedPoints,
    })),
  };
}
