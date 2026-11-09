// Pure helpers for the Accuracy and About pages (no I/O, unit-tested in scorecard.test.ts).
import { modelLabel } from "@/lib/models/labels";
import { barColor, SURFACE_TRACK, teamColors } from "@/lib/teams/colors";

import { formatPct, leagueMatches, roundLabel, teamName } from "./derive";
import { DRAW_BAR, nextMatchday } from "./home";
import type {
  BacktestRow,
  MatchRow,
  ScoredPrediction,
  ScoreRow,
} from "./types";

const LN3 = Math.log(3);
const ACCENT = "#7FA2FF";
const SILVER = "#C9D1E3";
export const UPSET = "#F5A35C";
export const LEAGUE_DAYS = [1, 2, 3, 4, 5, 6, 7, 8] as const;

// --- Season headline -----------------------------------------------------------------------------

/** Relative log-loss gain over guessing a third each: 1 − log loss / ln 3 (positive = better). */
export function seasonGain(logLoss: number): number {
  return 1 - logLoss / LN3;
}

/** A gain that would display as zero is zero: no "-0.0%", and no "worse" for a tie with guessing. */
export function normalizeGain(gain: number): number {
  return Math.abs(gain) < 0.0005 ? 0 : gain;
}

/** A gain to one decimal, e.g. "14.0%", "0.0%", "-2.3%". */
export function formatGain(gain: number): string {
  return formatPct(normalizeGain(gain), 1);
}

/** "26.1%" plus "better" or "worse": the honest wording either way. */
export function gainHeadline(rawGain: number): {
  value: string;
  word: "better" | "worse";
} {
  const gain = normalizeGain(rawGain);
  return {
    value: formatPct(Math.abs(gain), 1),
    word: gain >= 0 ? "better" : "worse",
  };
}

export function hitSummary(scored: Pick<ScoredPrediction, "hit">[]): {
  hits: number;
  n: number;
  share: number;
} {
  const hits = scored.filter((r) => r.hit).length;
  return {
    hits,
    n: scored.length,
    share: scored.length ? hits / scored.length : 0,
  };
}

// --- Model lanes ---------------------------------------------------------------------------------

export type Lane = {
  key: string;
  label: string;
  tag: string | null;
  logLoss: number;
  /** Share of the lane, log loss / 1.2, capped at 1. */
  width: number;
  color: string;
  emphasis: boolean;
};

export const LANE_SCALE = 1.2;

/** The main model (accent), the other live model (silver) and guessing; empty before any scores. */
export function modelLanes(scores: ScoreRow[]): Lane[] {
  const primary = scores.find((s) => s.isPrimary);
  if (!primary) return [];
  const other = scores.find((s) => !s.isPrimary);
  const lane = (
    key: string,
    label: string,
    logLoss: number,
    color: string,
    tag: string | null = null,
    emphasis = false,
  ): Lane => ({
    key,
    label,
    tag,
    logLoss,
    width: Math.min(1, logLoss / LANE_SCALE),
    color,
    emphasis,
  });
  return [
    lane(
      primary.model,
      modelLabel(primary.model, "live"),
      primary.logLoss,
      ACCENT,
      "main model",
      true,
    ),
    ...(other
      ? [
          lane(
            other.model,
            modelLabel(other.model, "live"),
            other.logLoss,
            SILVER,
          ),
        ]
      : []),
    lane("uniform", "Guessing", primary.uniformLogLoss, DRAW_BAR),
  ];
}

// --- Matchday tiles ------------------------------------------------------------------------------

export type MatchdayTile =
  | {
      matchday: number;
      state: "scored";
      hits: number;
      n: number;
      logLoss: number;
    }
  | { matchday: number; state: "beforeLaunch" }
  | { matchday: number; state: "next"; firstKickoff: string; locked: number }
  | { matchday: number; state: "upcoming" };

/**
 * One tile per league matchday: scored (it has scored predictions), played before launch (finished,
 * nothing scored), the next matchday (first kick-off, predictions locked in), or upcoming.
 */
export function matchdayTiles(
  matches: MatchRow[],
  scored: Pick<ScoredPrediction, "stage" | "matchday" | "hit" | "logLoss">[],
): MatchdayTile[] {
  const next = nextMatchday(matches);
  return LEAGUE_DAYS.map((md): MatchdayTile => {
    const rows = scored.filter(
      (s) => s.stage === "LEAGUE_PHASE" && s.matchday === md,
    );
    if (rows.length) {
      return {
        matchday: md,
        state: "scored",
        hits: rows.filter((r) => r.hit).length,
        n: rows.length,
        logLoss: rows.reduce((sum, r) => sum + r.logLoss, 0) / rows.length,
      };
    }
    const games = leagueMatches(matches, md);
    if (games.length && games.every((m) => m.status === "FINISHED"))
      return { matchday: md, state: "beforeLaunch" };
    if (md === next) {
      const kickoffs = games.map((m) => m.kickoff).sort();
      return {
        matchday: md,
        state: "next",
        firstKickoff: kickoffs[0],
        locked: games.filter((m) => m.prediction !== null).length,
      };
    }
    return { matchday: md, state: "upcoming" };
  });
}

// --- Calls that landed, upsets, every prediction ------------------------------------------------

type Call = Pick<
  ScoredPrediction,
  | "matchId"
  | "kickoff"
  | "home"
  | "away"
  | "outcome"
  | "predicted"
  | "pHome"
  | "pDraw"
  | "pAway"
  | "hit"
>;

const probOf = (r: Call, o: "H" | "D" | "A") =>
  o === "H" ? r.pHome : o === "D" ? r.pDraw : r.pAway;

/** The probability the model gave to what actually happened. */
export function outcomeProbability(r: Call): number {
  return probOf(r, r.outcome);
}

const newestFirst = (a: Call, b: Call) =>
  b.kickoff.localeCompare(a.kickoff) || b.matchId - a.matchId;

/** Hits where the model was surest of what happened; ties go to the newest match. */
export function landedCalls<T extends Call>(rows: T[], limit = 3): T[] {
  return rows
    .filter((r) => r.hit)
    .sort(
      (a, b) =>
        outcomeProbability(b) - outcomeProbability(a) || newestFirst(a, b),
    )
    .slice(0, limit);
}

/** Misses where what happened had the lowest probability; ties go to the newest match. */
export function upsets<T extends Call>(rows: T[], limit = 4): T[] {
  return rows
    .filter((r) => !r.hit)
    .sort(
      (a, b) =>
        outcomeProbability(a) - outcomeProbability(b) || newestFirst(a, b),
    )
    .slice(0, limit);
}

const sideName = (r: Call, o: "H" | "D" | "A") =>
  o === "H" ? teamName(r.home) : o === "A" ? teamName(r.away) : "the draw";

/** "Backed PSG 62%" (or "Backed the draw 31%"): the model's pick and its probability. */
export function backedLabel(r: Call): string {
  return `Backed ${sideName(r, r.predicted)} ${formatPct(probOf(r, r.predicted))}`;
}

/** The one-line note on a landed or upset card. */
export function callNote(r: Call): string {
  if (r.hit)
    return `Backed ${sideName(r, r.predicted)} at ${formatPct(probOf(r, r.predicted))}`;
  if (r.outcome === "D")
    return `A draw; ${sideName(r, r.predicted)} were ${formatPct(probOf(r, r.predicted))} favourites`;
  return `${sideName(r, r.outcome)} won with a ${formatPct(outcomeProbability(r))} chance`;
}

/** The card strip: the winner's colour at 3:1 on the card, or the draw grey. */
export function stripColor(r: Pick<Call, "home" | "away" | "outcome">): string {
  if (r.outcome === "D") return DRAW_BAR;
  const winner = r.outcome === "H" ? r.home : r.away;
  return barColor(winner, teamColors(winner).primary, SURFACE_TRACK);
}

export type ResultFilter = "all" | "hits" | "upsets";
export const ALL_ROUNDS = "all";

type Filterable = Pick<ScoredPrediction, "hit" | "stage" | "matchday">;

const inRound = (r: Filterable, round: string) =>
  round === ALL_ROUNDS || roundLabel(r) === round;

export function filterPredictions<T extends Filterable>(
  rows: T[],
  { result, round }: { result: ResultFilter; round: string },
): T[] {
  return rows.filter(
    (r) =>
      inRound(r, round) &&
      (result === "all" || (result === "hits" ? r.hit : !r.hit)),
  );
}

/** Counts for the filter buttons, within the selected round. */
export function predictionCounts(
  rows: Filterable[],
  round: string,
): Record<ResultFilter, number> {
  const shown = rows.filter((r) => inRound(r, round));
  const hits = shown.filter((r) => r.hit).length;
  return { all: shown.length, hits, upsets: shown.length - hits };
}

// --- Backtest ------------------------------------------------------------------------------------

export type GainBar = {
  model: string;
  label: string;
  gain: number;
  /** Bar length from zero, scaled to the best model. */
  width: number;
  role: BacktestRow["role"];
  isPrimary: boolean;
  color: string;
};

/** Gain over guessing per model on the whole test set: candidates first (best first), then baselines. */
export function backtestGainBars(rows: BacktestRow[]): GainBar[] {
  const overall = rows.filter((r) => r.scope === "overall");
  const gain = (r: BacktestRow) => normalizeGain(seasonGain(r.logLoss));
  const byGain = (a: BacktestRow, b: BacktestRow) => gain(b) - gain(a);
  const ordered = [
    ...overall.filter((r) => r.role === "candidate").sort(byGain),
    ...overall.filter((r) => r.role === "baseline").sort(byGain),
  ];
  const best = Math.max(0, ...ordered.map(gain)) || 1;
  return ordered.map((r) => ({
    model: r.model,
    label: modelLabel(r.model, "backtest"),
    gain: gain(r),
    width: Math.max(0, gain(r)) / best,
    role: r.role,
    isPrimary: r.isPrimary,
    color: r.isPrimary ? ACCENT : r.role === "baseline" ? DRAW_BAR : SILVER,
  }));
}

// --- About ---------------------------------------------------------------------------------------

/** Roving tabindex for the timeline tabs: the index to move to, or null for other keys. */
export function timelineKey(
  index: number,
  key: string,
  count: number,
): number | null {
  switch (key) {
    case "ArrowRight":
      return (index + 1) % count;
    case "ArrowLeft":
      return (index - 1 + count) % count;
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}

const THOUSANDS: Record<number, string> = {
  1000: "one thousand",
  5000: "five thousand",
  10000: "ten thousand",
  20000: "twenty thousand",
  50000: "fifty thousand",
  100000: "a hundred thousand",
};

/** "ten thousand" for a round count, digits otherwise. */
export function simsInWords(n: number): string {
  return THOUSANDS[n] ?? n.toLocaleString("en-GB");
}
