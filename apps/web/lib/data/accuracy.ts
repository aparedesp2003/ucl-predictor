import "server-only";

import { and, eq, sql } from "drizzle-orm";
import { cacheLife, cacheTag } from "next/cache";

import { getDb } from "@/lib/db";
import {
  type RawCalibrationBin,
  webBacktestSummary as b,
  webPredictionScores as v,
} from "@/lib/db/schema";

import type { CacheTag } from "./tags";
import type {
  Backtest,
  BacktestRow,
  CalibrationBin,
  Outcome,
  ScoredPrediction,
} from "./types";

/** The current season: the newest one the web can see. */
export async function getCurrentSeason(): Promise<string | null> {
  "use cache";
  cacheTag("matches" satisfies CacheTag);
  cacheLife("hours");

  const [row] = await getDb().execute<{ season: string | null }>(
    sql`SELECT max(season) AS season FROM web_match_predictions`,
  );
  return row?.season ?? null;
}

/** The primary model's scored predictions for one season, newest kick-off first. */
export async function getScoredPredictions(
  season: string,
): Promise<ScoredPrediction[]> {
  "use cache";
  cacheTag("scoreboard" satisfies CacheTag);
  cacheLife("hours");

  const rows = await getDb()
    .select()
    .from(v)
    .where(and(eq(v.season, season), eq(v.isPrimary, true)));

  return rows.map((r) => ({
    matchId: r.matchId,
    model: r.model,
    stage: r.stage,
    matchday: r.matchday,
    kickoff: r.kickoffUtc?.toISOString() ?? `${r.matchDate}T00:00:00.000Z`,
    home: {
      id: r.homeTeamId,
      fdId: r.homeFdTeamId,
      name: r.homeName,
      shortName: r.homeShortName,
      tla: r.homeTla,
    },
    away: {
      id: r.awayTeamId,
      fdId: r.awayFdTeamId,
      name: r.awayName,
      shortName: r.awayShortName,
      tla: r.awayTla,
    },
    homeGoals: r.homeGoals90,
    awayGoals: r.awayGoals90,
    outcome: r.outcome as Outcome,
    predicted: r.predicted as Outcome,
    pHome: r.pHome,
    pDraw: r.pDraw,
    pAway: r.pAway,
    logLoss: r.logLoss,
    rps: r.rps,
    hit: r.hit,
  }));
}

const bins = (raw: RawCalibrationBin[] | null): CalibrationBin[] | null =>
  raw?.map((x) => ({
    lo: x.lo,
    hi: x.hi,
    n: x.n,
    meanPred: x.mean_pred,
    observed: x.observed,
  })) ?? null;

/** Test-season results of the latest backtest per model; null before any backtest has run. */
export async function getBacktest(): Promise<Backtest | null> {
  "use cache";
  cacheTag("backtest" satisfies CacheTag);
  cacheLife("days");

  const rows = await getDb().select().from(b);
  if (!rows.length) return null;

  const primary = rows.find((r) => r.isPrimary && r.scope === "overall");
  return {
    rows: rows.map((r): BacktestRow => ({
      model: r.model,
      role: r.role === "baseline" ? "baseline" : "candidate",
      scope: r.scope,
      n: r.n,
      logLoss: r.logLoss,
      rps: r.rps,
      brier: r.brier,
      accuracy: r.accuracy,
      isPrimary: r.isPrimary,
    })),
    calibration: primary
      ? {
          model: primary.model,
          home: bins(primary.calibrationHome),
          away: bins(primary.calibrationAway),
        }
      : null,
  };
}
