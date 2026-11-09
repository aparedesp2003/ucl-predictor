import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  biggestCalls,
  currentMatchday,
  favoured,
  formatPct,
  formatSimPct,
  improvementOverGuessing,
  isHit,
  roundLabel,
  sortRows,
  titleHeadline,
} from "./derive";
import type { MatchRow, TitleOdds } from "./types";

const team = { id: 1, fdId: null, name: "Team", shortName: null, tla: null };

function match(over: Partial<MatchRow> = {}): MatchRow {
  return {
    id: 1,
    season: "2026-27",
    stage: "LEAGUE_PHASE",
    matchday: 1,
    leg: null,
    kickoff: "2026-09-08T19:00:00.000Z",
    status: "SCHEDULED",
    homeGoals: null,
    awayGoals: null,
    home: team,
    away: team,
    prediction: null,
    ...over,
  };
}

const pred = (pHome: number, pDraw: number, pAway: number) => ({
  pHome,
  pDraw,
  pAway,
  model: "elo",
  predictedAt: "2026-09-01T00:00:00.000Z",
});

describe("currentMatchday", () => {
  it("is the lowest matchday with a match still to play", () => {
    const matches = [
      match({ matchday: 1, status: "FINISHED" }),
      match({ matchday: 3, status: "SCHEDULED" }),
      match({ matchday: 2, status: "SCHEDULED" }),
    ];
    expect(currentMatchday(matches)).toBe(2);
  });

  it("is the last matchday once everything is played, and 1 with no data", () => {
    expect(currentMatchday([match({ matchday: 8, status: "FINISHED" })])).toBe(
      8,
    );
    expect(currentMatchday([])).toBe(1);
  });

  it("ignores knockout matches", () => {
    const matches = [
      match({ matchday: 8, status: "FINISHED" }),
      match({ stage: "LAST_16", matchday: 9, status: "SCHEDULED" }),
    ];
    expect(currentMatchday(matches)).toBe(8);
  });
});

describe("favoured / isHit", () => {
  it("breaks ties towards home, then draw", () => {
    expect(favoured(pred(0.4, 0.4, 0.2))).toBe("H");
    expect(favoured(pred(0.2, 0.4, 0.4))).toBe("D");
    expect(favoured(pred(0.2, 0.3, 0.5))).toBe("A");
  });

  it("scores finished, predicted matches only", () => {
    const finished = { status: "FINISHED", homeGoals: 2, awayGoals: 0 };
    expect(isHit(match({ ...finished, prediction: pred(0.5, 0.3, 0.2) }))).toBe(
      true,
    );
    expect(isHit(match({ ...finished, prediction: pred(0.2, 0.3, 0.5) }))).toBe(
      false,
    );
    expect(isHit(match(finished))).toBeNull();
    expect(isHit(match({ prediction: pred(0.5, 0.3, 0.2) }))).toBeNull();
  });
});

describe("biggestCalls", () => {
  it("sorts predicted matches by the strongest side and skips unpredicted ones", () => {
    const calls = biggestCalls([
      match({ id: 1, prediction: pred(0.5, 0.3, 0.2) }),
      match({ id: 2 }),
      match({ id: 3, prediction: pred(0.1, 0.2, 0.7) }),
      match({ id: 4, prediction: pred(0.6, 0.2, 0.2) }),
    ]);
    expect(calls.map((m) => m.id)).toEqual([3, 4, 1]);
  });
});

describe("titleHeadline", () => {
  const odds = (name: string, pWin: number) =>
    ({ team: { ...team, name }, pWin }) as TitleOdds;

  it("names the favourite", () => {
    expect(titleHeadline([odds("Arsenal", 0.3), odds("Bayern", 0.2)])).toBe(
      "Arsenal are the team to beat",
    );
    expect(titleHeadline([odds("Arsenal", 0.4), odds("Bayern", 0.1)])).toBe(
      "Arsenal are the clear team to beat",
    );
    expect(titleHeadline([odds("Arsenal", 0.21), odds("Bayern", 0.2)])).toBe(
      "Arsenal and Bayern are level at the top of the title odds",
    );
    expect(titleHeadline([])).toBeNull();
  });
});

describe("numbers", () => {
  it("formats percentages", () => {
    expect(formatPct(0.523)).toBe("52%");
    expect(formatPct(0.004)).toBe("<1%");
    expect(formatPct(0)).toBe("0%");
    expect(formatPct(0.1234, 1)).toBe("12.3%");
    expect(formatPct(0.996)).toBe(">99%");
    expect(formatPct(0.994)).toBe("99%");
    expect(formatPct(1)).toBe("100%");
    expect(formatPct(0.9996, 1)).toBe(">99.9%");
  });

  it("computes the log-loss improvement over guessing", () => {
    expect(
      improvementOverGuessing({ logLoss: 0.99, uniformLogLoss: 1.1 }),
    ).toBeCloseTo(0.1);
  });
});

// The same cases drive the engine's integration test of web_prediction_scores.hit, so the Matches
// page and the Accuracy page cannot disagree on what a hit is.
type HitCase = {
  case: string;
  p_home: number;
  p_draw: number;
  p_away: number;
  home_goals: number;
  away_goals: number;
  hit: boolean;
};
const HIT_CASES: HitCase[] = JSON.parse(
  readFileSync(
    path.resolve(__dirname, "../../../engine/tests/fixtures/hit_cases.json"),
    "utf-8",
  ),
);

describe("isHit agrees with web_prediction_scores.hit", () => {
  it("covers a draw-favoured match and every tie", () => {
    const names = HIT_CASES.map((c) => c.case).join(" | ");
    expect(names).toContain("draw favoured");
    expect(names).toContain("tie");
  });

  it.each(HIT_CASES)("$case", (c) => {
    const m = match({
      status: "FINISHED",
      homeGoals: c.home_goals,
      awayGoals: c.away_goals,
      prediction: pred(c.p_home, c.p_draw, c.p_away),
    });
    expect(isHit(m)).toBe(c.hit);
  });
});

describe("formatSimPct", () => {
  it("never shows 0% or 100%", () => {
    expect(formatSimPct(0)).toBe("<1%");
    expect(formatSimPct(0.009)).toBe("<1%");
    expect(formatSimPct(1)).toBe(">99%");
    expect(formatSimPct(0.996)).toBe(">99%");
  });

  it("rounds everything else to whole percentages", () => {
    expect(formatSimPct(0.01)).toBe("1%");
    expect(formatSimPct(0.426)).toBe("43%");
    expect(formatSimPct(0.994)).toBe("99%");
  });
});

describe("sortRows", () => {
  const rows = [
    { name: "b", v: 2 },
    { name: "a", v: 1 },
    { name: "c", v: 2 },
  ];

  it("sorts numbers both ways and keeps ties stable", () => {
    expect(sortRows(rows, (r) => r.v, "desc").map((r) => r.name)).toEqual([
      "b",
      "c",
      "a",
    ]);
    expect(sortRows(rows, (r) => r.v, "asc").map((r) => r.name)).toEqual([
      "a",
      "b",
      "c",
    ]);
  });

  it("sorts strings and leaves the input alone", () => {
    expect(sortRows(rows, (r) => r.name, "desc").map((r) => r.name)).toEqual([
      "c",
      "b",
      "a",
    ]);
    expect(rows[0].name).toBe("b");
  });
});

describe("roundLabel", () => {
  it("names league matchdays and knockout rounds", () => {
    expect(roundLabel({ stage: "LEAGUE_PHASE", matchday: 3 })).toBe(
      "Matchday 3",
    );
    expect(roundLabel({ stage: "LAST_16", matchday: null })).toBe("Last 16");
  });
});
