// Pure helpers over lib/data results (no I/O, unit-tested).
import { LEAGUE_MATCHDAYS } from "@/lib/site";

import type {
  MatchRow,
  Outcome,
  Prediction,
  ScoreRow,
  TitleOdds,
} from "./types";

const LEAGUE_PHASE = "LEAGUE_PHASE";

export function leagueMatches(
  matches: MatchRow[],
  matchday?: number,
): MatchRow[] {
  return matches.filter(
    (m) =>
      m.stage === LEAGUE_PHASE &&
      (matchday === undefined || m.matchday === matchday),
  );
}

/** The lowest league matchday that still has a match to play; the last one once all are done. */
export function currentMatchday(matches: MatchRow[]): number {
  const league = leagueMatches(matches).filter((m) => m.matchday !== null);
  const open = league.filter(
    (m) => m.status === "SCHEDULED" || m.status === "POSTPONED",
  );
  const days = (open.length ? open : league).map((m) => m.matchday as number);
  if (!days.length) return 1;
  const day = open.length ? Math.min(...days) : Math.max(...days);
  return Math.min(Math.max(day, 1), LEAGUE_MATCHDAYS);
}

/** 90-minute result, or null when the match has no final score. */
export function outcome(m: MatchRow): Outcome | null {
  if (m.status !== "FINISHED" || m.homeGoals === null || m.awayGoals === null)
    return null;
  return m.homeGoals > m.awayGoals
    ? "H"
    : m.homeGoals === m.awayGoals
      ? "D"
      : "A";
}

/** The outcome the model rated most likely; ties go to home, then draw (as in the engine). */
export function favoured(
  p: Pick<Prediction, "pHome" | "pDraw" | "pAway">,
): Outcome {
  if (p.pHome >= p.pDraw && p.pHome >= p.pAway) return "H";
  return p.pDraw >= p.pAway ? "D" : "A";
}

/** true/false once the match is decided and predicted; null otherwise. */
export function isHit(m: MatchRow): boolean | null {
  const result = outcome(m);
  if (!result || !m.prediction) return null;
  return favoured(m.prediction) === result;
}

/** Kicked off (or otherwise no longer scheduled), so the prediction is final. */
export function isLocked(m: MatchRow, now = Date.now()): boolean {
  return m.status !== "SCHEDULED" || Date.parse(m.kickoff) <= now;
}

/** Predicted matches sorted by how strongly the model backs one side. */
export function biggestCalls(matches: MatchRow[], limit = 6): MatchRow[] {
  const strength = (m: MatchRow) =>
    Math.max(m.prediction!.pHome, m.prediction!.pAway);
  return matches
    .filter((m) => m.prediction)
    .sort(
      (a, b) => strength(b) - strength(a) || a.kickoff.localeCompare(b.kickoff),
    )
    .slice(0, limit);
}

export function kickoffRange(
  matches: MatchRow[],
): { first: string; last: string } | null {
  if (!matches.length) return null;
  const sorted = matches.map((m) => m.kickoff).sort();
  return { first: sorted[0], last: sorted[sorted.length - 1] };
}

/** Relative log-loss improvement over always guessing 1/3 each (positive = better). */
export function improvementOverGuessing(
  row: Pick<ScoreRow, "logLoss" | "uniformLogLoss">,
) {
  return (row.uniformLogLoss - row.logLoss) / row.uniformLogLoss;
}

export function teamName(team: {
  name: string;
  shortName: string | null;
}): string {
  return team.shortName ?? team.name;
}

/** A one-line headline from the title odds; null when there are none. */
export function titleHeadline(teams: TitleOdds[]): string | null {
  const [leader, second] = teams;
  if (!leader) return null;
  const name = teamName(leader.team);
  if (!second) return `${name} are the team to beat`;
  if (leader.pWin - second.pWin < 0.02) {
    return `${name} and ${teamName(second.team)} are level at the top of the title odds`;
  }
  if (leader.pWin >= 2 * second.pWin)
    return `${name} are the clear team to beat`;
  return `${name} are the team to beat`;
}

export function formatPct(p: number, digits = 0): string {
  if (p > 0 && p < 0.01 && digits === 0) return "<1%";
  // Never round a non-certain probability up to 100%.
  const top = 100 - 10 ** -digits;
  if (p < 1 && p * 100 >= top + 10 ** -digits / 2) return `>${top.toFixed(digits)}%`;
  return `${(p * 100).toFixed(digits)}%`;
}
