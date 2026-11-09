// Pure helpers for the Home page (no I/O, unit-tested in home.test.ts).
import { CLASH_DISTANCE, rgbDistance, teamColors } from "@/lib/teams/colors";

import {
  biggestCalls,
  currentMatchday,
  favoured,
  isLocked,
  leagueMatches,
  teamName,
} from "./derive";
import type {
  MatchRow,
  Outcome,
  Prediction,
  ScoredPrediction,
  TeamRef,
  TitleOdds,
} from "./types";

export type PredictedMatch = MatchRow & { prediction: Prediction };

const hasPrediction = (m: MatchRow): m is PredictedMatch =>
  m.prediction !== null;

/** The matchday still to be played (it has a scheduled match), or null once the league phase is done. */
export function nextMatchday(matches: MatchRow[]): number | null {
  const md = currentMatchday(matches);
  return leagueMatches(matches, md).some((m) => m.status === "SCHEDULED")
    ? md
    : null;
}

/** Every fixture of a matchday, in kick-off order. */
export function matchdayFixtures(matches: MatchRow[], md: number): MatchRow[] {
  return leagueMatches(matches, md).sort(
    (a, b) => a.kickoff.localeCompare(b.kickoff) || a.id - b.id,
  );
}

/**
 * The closest call: among predicted fixtures not yet kicked off, the one whose likeliest outcome is
 * least likely (smallest max of home, draw and away). Ties go to the earliest kick-off.
 */
export function closestCall(
  fixtures: MatchRow[],
  now = Date.now(),
): PredictedMatch | null {
  const open = fixtures.filter(hasPrediction).filter((m) => !isLocked(m, now));
  const top = (m: PredictedMatch) =>
    Math.max(m.prediction.pHome, m.prediction.pDraw, m.prediction.pAway);
  const [best] = open.sort(
    (a, b) =>
      top(a) - top(b) || a.kickoff.localeCompare(b.kickoff) || a.id - b.id,
  );
  return best ?? null;
}

/** The six fixtures the model backs one side most strongly in (by max of home and away win). */
export function boldestCalls(
  fixtures: MatchRow[],
  limit = 6,
): PredictedMatch[] {
  return biggestCalls(fixtures, limit) as PredictedMatch[];
}

/** The side the model favours between the two teams (draw aside); ties go home. */
export function favouriteSide(
  p: Pick<Prediction, "pHome" | "pAway">,
): "H" | "A" {
  return p.pHome >= p.pAway ? "H" : "A";
}

/** One ticker item: codes come from the caller (display map), the favoured outcome is flagged. */
export function tickerOutcomes(
  p: Pick<Prediction, "pHome" | "pDraw" | "pAway">,
): { outcome: Outcome; p: number; favoured: boolean }[] {
  const fav = favoured(p);
  return (
    [
      ["H", p.pHome],
      ["D", p.pDraw],
      ["A", p.pAway],
    ] as const
  ).map(([outcome, value]) => ({
    outcome,
    p: value,
    favoured: outcome === fav,
  }));
}

/** A whole-number percentage for the ticker and cards, never 0% or 100%. */
export function pct(p: number): string {
  return `${Math.min(99, Math.max(1, Math.round(p * 100)))}`;
}

// --- The race for the trophy -------------------------------------------------------------------

export const RACE_METRICS = [
  { key: "pR16", label: "Last 16", long: "chance of reaching the last 16" },
  { key: "pSf", label: "Semis", long: "chance of reaching the semi-finals" },
  { key: "pFinal", label: "Final", long: "chance of reaching the final" },
  { key: "pWin", label: "Win", long: "chance to win the competition" },
] as const;

export type RaceMetric = (typeof RACE_METRICS)[number]["key"];

/** The top teams by one metric, highest first; ties by win chance, then name. */
export function raceTop(
  teams: TitleOdds[],
  metric: RaceMetric,
  limit = 8,
): TitleOdds[] {
  return [...teams]
    .sort(
      (a, b) =>
        b[metric] - a[metric] ||
        b.pWin - a.pWin ||
        teamName(a.team).localeCompare(teamName(b.team)),
    )
    .slice(0, limit);
}

/**
 * Bar colours down the race: each team's primary, except that a team switches to its secondary when
 * its primary clashes with the colour shown on the row above (the same rule as clashColors).
 */
export function raceColors(teams: Pick<TeamRef, "tla" | "name">[]): string[] {
  const out: string[] = [];
  for (const team of teams) {
    const c = teamColors(team);
    const above = out[out.length - 1];
    out.push(
      above && rgbDistance(above, c.primary) < CLASH_DISTANCE
        ? c.secondary
        : c.primary,
    );
  }
  return out;
}

/** ">99%" and "<1%" at the ends, one decimal under 10%, whole numbers otherwise. */
export function formatRacePct(p: number): string {
  const v = p * 100;
  if (v >= 99.5) return ">99%";
  if (v < 1) return "<1%";
  if (Math.round(v * 10) / 10 < 10) return `${v.toFixed(1)}%`;
  return `${Math.round(v)}%`;
}

// --- Report card --------------------------------------------------------------------------------

/** The latest league matchday that is fully played and has scored predictions; null before any. */
export function lastCompletedMatchday(
  matches: MatchRow[],
  scored: Pick<ScoredPrediction, "stage" | "matchday">[],
): number | null {
  const scoredDays = new Set(
    scored
      .filter((s) => s.stage === "LEAGUE_PHASE" && s.matchday !== null)
      .map((s) => s.matchday as number),
  );
  const done = [...scoredDays].filter((md) => {
    const games = leagueMatches(matches, md);
    return games.length > 0 && games.every((m) => m.status === "FINISHED");
  });
  return done.length ? Math.max(...done) : null;
}

export type ReportDot = { matchId: number; hit: boolean; label: string };

export type ReportCard = {
  matchday: number;
  hits: number;
  n: number;
  logLoss: number;
  /** Relative log-loss improvement over a third each (positive = better). */
  gain: number;
  dots: ReportDot[];
};

/** How the primary model's favourites did on one matchday, one dot per match in kick-off order. */
export function reportCard(
  scored: ScoredPrediction[],
  matchday: number,
): ReportCard | null {
  const rows = scored
    .filter((s) => s.stage === "LEAGUE_PHASE" && s.matchday === matchday)
    .sort(
      (a, b) => a.kickoff.localeCompare(b.kickoff) || a.matchId - b.matchId,
    );
  if (!rows.length) return null;
  const logLoss = rows.reduce((sum, r) => sum + r.logLoss, 0) / rows.length;
  const guess = Math.log(3);
  return {
    matchday,
    hits: rows.filter((r) => r.hit).length,
    n: rows.length,
    logLoss,
    gain: (guess - logLoss) / guess,
    dots: rows.map((r) => ({
      matchId: r.matchId,
      hit: r.hit,
      label: `${teamName(r.home)} ${r.homeGoals}–${r.awayGoals} ${teamName(r.away)}, ${r.hit ? "favourite won" : "upset"}`,
    })),
  };
}

// --- Countdown ----------------------------------------------------------------------------------

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export type CountdownParts =
  | { done: true }
  | {
      done: false;
      days: number;
      hours: number;
      minutes: number;
      /** Only in the final hour; until then the countdown moves once a minute (WCAG 2.2.2). */
      seconds: number | null;
      /** Milliseconds until the display next changes. */
      nextTickMs: number;
    };

export function countdownParts(msLeft: number): CountdownParts {
  if (msLeft <= 0) return { done: true };
  const finalHour = msLeft <= HOUR;
  const days = Math.floor(msLeft / DAY);
  const hours = Math.floor((msLeft % DAY) / HOUR);
  const minutes = Math.floor((msLeft % HOUR) / MINUTE);
  const seconds = finalHour ? Math.floor((msLeft % MINUTE) / 1000) : null;
  const step = finalHour ? 1000 : MINUTE;
  return {
    done: false,
    days,
    hours,
    minutes,
    seconds,
    nextTickMs: msLeft % step || step,
  };
}

/** Screen-reader text, changing at most once a minute. */
export function countdownLabel(msLeft: number): string {
  const parts = countdownParts(msLeft);
  if (parts.done) return "Kicked off, prediction locked";
  const unit = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
  const bits = [
    parts.days ? unit(parts.days, "day") : null,
    parts.days || parts.hours ? unit(parts.hours, "hour") : null,
    unit(parts.minutes, "minute"),
  ].filter(Boolean);
  return `${bits.join(" ")} to kick-off`;
}
