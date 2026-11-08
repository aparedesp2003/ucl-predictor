import "server-only";

import { eq, sql } from "drizzle-orm";
import { cacheLife, cacheTag } from "next/cache";

import { getDb } from "@/lib/db";
import { webMatchPredictions as v } from "@/lib/db/schema";

import type { CacheTag } from "./tags";
import type { MatchRow } from "./types";

/** Every match of the current (newest) season, in kick-off order. */
export async function getSeasonMatches(): Promise<MatchRow[]> {
  "use cache";
  cacheTag("matches" satisfies CacheTag);
  cacheLife("hours");

  const rows = await getDb()
    .select()
    .from(v)
    .where(eq(v.season, sql`(SELECT max(season) FROM web_match_predictions)`));

  return rows.map((r) => ({
    id: r.matchId,
    season: r.season,
    stage: r.stage,
    matchday: r.matchday,
    leg: r.leg,
    kickoff: r.kickoffUtc?.toISOString() ?? `${r.matchDate}T00:00:00.000Z`,
    status: r.status,
    homeGoals: r.homeGoals90,
    awayGoals: r.awayGoals90,
    home: {
      id: r.homeTeamId,
      name: r.homeName,
      shortName: r.homeShortName,
      tla: r.homeTla,
    },
    away: {
      id: r.awayTeamId,
      name: r.awayName,
      shortName: r.awayShortName,
      tla: r.awayTla,
    },
    prediction:
      r.pHome !== null &&
      r.pDraw !== null &&
      r.pAway !== null &&
      r.model &&
      r.predictedAt
        ? {
            pHome: r.pHome,
            pDraw: r.pDraw,
            pAway: r.pAway,
            model: r.model,
            predictedAt: r.predictedAt.toISOString(),
          }
        : null,
  }));
}
