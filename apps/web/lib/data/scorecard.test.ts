import { describe, expect, it } from "vitest";

import { contrastRatio, SURFACE_TRACK } from "@/lib/teams/colors";

import { DRAW_BAR } from "./home";
import {
  ALL_ROUNDS,
  backedLabel,
  backtestGainBars,
  callNote,
  filterPredictions,
  gainHeadline,
  hitSummary,
  landedCalls,
  matchdayTiles,
  modelLanes,
  predictionCounts,
  seasonGain,
  simsInWords,
  stripColor,
  timelineKey,
  upsets,
} from "./scorecard";
import type {
  BacktestRow,
  MatchRow,
  ScoredPrediction,
  ScoreRow,
  TeamRef,
} from "./types";

const team = (tla: string, name = tla): TeamRef => ({
  id: tla.charCodeAt(0) * 100 + tla.charCodeAt(1),
  fdId: null,
  name,
  shortName: name,
  tla,
});

let nextId = 1;

function scored(over: Partial<ScoredPrediction> = {}): ScoredPrediction {
  const base: ScoredPrediction = {
    matchId: nextId++,
    model: "elo",
    stage: "LEAGUE_PHASE",
    matchday: 1,
    kickoff: "2026-09-16T19:00:00.000Z",
    home: team("PSG", "PSG"),
    away: team("ARS", "Arsenal"),
    homeGoals: 2,
    awayGoals: 1,
    outcome: "H",
    predicted: "H",
    pHome: 0.5,
    pDraw: 0.25,
    pAway: 0.25,
    logLoss: 0.69,
    rps: 0.1,
    hit: true,
  };
  const r = { ...base, ...over };
  return { ...r, hit: over.hit ?? r.predicted === r.outcome };
}

function match(over: Partial<MatchRow> = {}): MatchRow {
  return {
    id: nextId++,
    season: "2026-27",
    stage: "LEAGUE_PHASE",
    matchday: 1,
    leg: null,
    kickoff: "2026-09-16T19:00:00.000Z",
    status: "FINISHED",
    homeGoals: 1,
    awayGoals: 0,
    home: team("PSG"),
    away: team("ARS"),
    prediction: null,
    ...over,
  };
}

const prediction = {
  pHome: 0.5,
  pDraw: 0.3,
  pAway: 0.2,
  model: "elo",
  predictedAt: "2026-11-20T06:15:00.000Z",
};

describe("season headline", () => {
  it("is the relative gain over guessing", () => {
    expect(seasonGain(Math.log(3))).toBeCloseTo(0);
    expect(seasonGain(0.759)).toBeCloseTo(1 - 0.759 / Math.log(3));
    expect(gainHeadline(seasonGain(0.759))).toEqual({
      value: "30.9%",
      word: "better",
    });
  });

  it("says worse than guessing honestly", () => {
    expect(gainHeadline(seasonGain(1.2))).toEqual({
      value: "9.2%",
      word: "worse",
    });
  });

  it("counts favourites that came through", () => {
    expect(
      hitSummary([{ hit: true }, { hit: false }, { hit: true }, { hit: true }]),
    ).toEqual({
      hits: 3,
      n: 4,
      share: 0.75,
    });
    expect(hitSummary([])).toEqual({ hits: 0, n: 0, share: 0 });
  });
});

describe("model lanes", () => {
  const row = (
    model: string,
    logLoss: number,
    isPrimary: boolean,
  ): ScoreRow => ({
    model,
    season: "2026-27",
    n: 18,
    logLoss,
    rps: 0.2,
    accuracy: 0.6,
    uniformLogLoss: Math.log(3),
    uniformRps: 0.27,
    uniformAccuracy: 0.44,
    isPrimary,
  });

  it("puts the main model first, then the other model and guessing", () => {
    const lanes = modelLanes([
      row("poisson_shrink", 0.801, false),
      row("elo", 0.759, true),
    ]);
    expect(lanes.map((l) => [l.label, l.tag])).toEqual([
      ["Elo", "main model"],
      ["Poisson", null],
      ["Guessing", null],
    ]);
    expect(lanes[0].width).toBeCloseTo(0.759 / 1.2);
    expect(lanes[2].width).toBeCloseTo(Math.log(3) / 1.2);
    expect(lanes[2].color).toBe(DRAW_BAR);
  });

  it("caps the lane at 1.2 and is empty before any score", () => {
    expect(modelLanes([row("elo", 1.5, true)])[0].width).toBe(1);
    expect(modelLanes([])).toEqual([]);
  });
});

describe("matchday tiles", () => {
  it("tells scored, before-launch, next and upcoming matchdays apart", () => {
    const matches = [
      match({ matchday: 1 }),
      match({ matchday: 2 }),
      match({
        matchday: 3,
        status: "SCHEDULED",
        kickoff: "2026-11-25T20:00:00.000Z",
        prediction,
      }),
      match({
        matchday: 3,
        status: "SCHEDULED",
        kickoff: "2026-11-24T17:45:00.000Z",
        prediction,
      }),
      match({
        matchday: 3,
        status: "SCHEDULED",
        kickoff: "2026-11-25T17:45:00.000Z",
      }),
      match({ matchday: 4, status: "SCHEDULED", prediction }),
    ];
    const rows = [
      scored({ matchday: 2, logLoss: 0.5 }),
      scored({ matchday: 2, logLoss: 1.1, predicted: "A" }),
    ];
    const tiles = matchdayTiles(matches, rows);
    expect(tiles).toHaveLength(8);
    expect(tiles[0]).toEqual({ matchday: 1, state: "beforeLaunch" });
    expect(tiles[1]).toMatchObject({
      matchday: 2,
      state: "scored",
      hits: 1,
      n: 2,
    });
    if (tiles[1].state === "scored") expect(tiles[1].logLoss).toBeCloseTo(0.8);
    expect(tiles[2]).toEqual({
      matchday: 3,
      state: "next",
      firstKickoff: "2026-11-24T17:45:00.000Z",
      locked: 2,
    });
    expect(tiles.slice(3).every((t) => t.state === "upcoming")).toBe(true);
  });

  it("are all upcoming with no fixtures", () => {
    expect(matchdayTiles([], []).every((t) => t.state === "upcoming")).toBe(
      true,
    );
  });
});

describe("calls that landed and upsets", () => {
  const rows = [
    scored({ pHome: 0.8, pDraw: 0.1, pAway: 0.1 }), // hit, 80% on what happened
    scored({
      pHome: 0.6,
      pDraw: 0.2,
      pAway: 0.2,
      kickoff: "2026-10-01T19:00:00.000Z",
    }),
    scored({
      pHome: 0.6,
      pDraw: 0.2,
      pAway: 0.2,
      kickoff: "2026-10-22T19:00:00.000Z",
    }), // tie, newer
    scored({ pHome: 0.45, pDraw: 0.3, pAway: 0.25 }),
    // Upsets: the probability on what happened.
    scored({
      outcome: "A",
      homeGoals: 0,
      awayGoals: 2,
      pHome: 0.7,
      pDraw: 0.2,
      pAway: 0.1,
    }), // 10%
    scored({
      outcome: "D",
      homeGoals: 1,
      awayGoals: 1,
      pHome: 0.6,
      pDraw: 0.25,
      pAway: 0.15,
    }), // 25%
    scored({
      outcome: "A",
      homeGoals: 0,
      awayGoals: 1,
      pHome: 0.55,
      pDraw: 0.3,
      pAway: 0.15,
    }), // 15%
    scored({
      outcome: "A",
      homeGoals: 1,
      awayGoals: 3,
      pHome: 0.4,
      pDraw: 0.3,
      pAway: 0.3,
    }), // 30%
    scored({
      outcome: "H",
      homeGoals: 1,
      awayGoals: 0,
      predicted: "D",
      pHome: 0.33,
      pDraw: 0.34,
      pAway: 0.33,
    }), // 33%
  ];

  it("picks the three surest hits, newest first on ties", () => {
    const landed = landedCalls(rows);
    expect(landed.map((r) => r.pHome)).toEqual([0.8, 0.6, 0.6]);
    expect(landed[1].kickoff).toBe("2026-10-22T19:00:00.000Z");
  });

  it("picks up to four upsets, least likely first", () => {
    const got = upsets(rows).map((r) => [
      r.outcome,
      r.outcome === "A" ? r.pAway : r.outcome === "D" ? r.pDraw : r.pHome,
    ]);
    expect(got).toEqual([
      ["A", 0.1],
      ["A", 0.15],
      ["D", 0.25],
      ["A", 0.3],
    ]);
    expect(upsets([rows[0]])).toEqual([]);
  });

  it("words each kind of card", () => {
    expect(callNote(rows[0])).toBe("Backed PSG at 80%");
    expect(callNote(rows[4])).toBe("Arsenal won with a 10% chance");
    expect(callNote(rows[5])).toBe("A draw; PSG were 60% favourites");
    expect(callNote(rows[8])).toBe("PSG won with a 33% chance");
    expect(
      callNote(
        scored({
          outcome: "D",
          predicted: "D",
          pDraw: 0.36,
          pHome: 0.32,
          pAway: 0.32,
        }),
      ),
    ).toBe("Backed the draw at 36%");
    expect(backedLabel(rows[4])).toBe("Backed PSG 70%");
    expect(backedLabel(rows[8])).toBe("Backed the draw 34%");
  });

  it("colours the strip by the winner, readable on the card", () => {
    expect(stripColor(rows[5])).toBe(DRAW_BAR);
    for (const r of rows)
      expect(
        contrastRatio(stripColor(r), SURFACE_TRACK),
      ).toBeGreaterThanOrEqual(3);
  });
});

describe("prediction filters", () => {
  const rows = [
    scored({ matchday: 1 }),
    scored({ matchday: 1, predicted: "A" }),
    scored({ matchday: 2 }),
    scored({ matchday: 2 }),
    scored({ matchday: 2, predicted: "D" }),
  ];

  it("counts all, hits and upsets within the round", () => {
    expect(predictionCounts(rows, ALL_ROUNDS)).toEqual({
      all: 5,
      hits: 3,
      upsets: 2,
    });
    expect(predictionCounts(rows, "Matchday 2")).toEqual({
      all: 3,
      hits: 2,
      upsets: 1,
    });
  });

  it("filters by result and round together", () => {
    expect(
      filterPredictions(rows, { result: "hits", round: ALL_ROUNDS }),
    ).toHaveLength(3);
    expect(
      filterPredictions(rows, { result: "upsets", round: "Matchday 1" }),
    ).toEqual([rows[1]]);
    expect(
      filterPredictions(rows, { result: "all", round: "Matchday 2" }),
    ).toEqual(rows.slice(2));
  });
});

describe("backtest gain bars", () => {
  const bt = (
    model: string,
    logLoss: number,
    role: "candidate" | "baseline",
    isPrimary = false,
  ): BacktestRow => ({
    model,
    role,
    scope: "overall",
    n: 753,
    logLoss,
    rps: 0.2,
    brier: 0.55,
    accuracy: 0.57,
    isPrimary,
  });
  const rows = [
    bt("uniform", Math.log(3), "baseline"),
    bt("poisson", 0.949, "candidate"),
    bt("elo", 0.945, "candidate", true),
    bt("historical", 1.03, "baseline"),
    { ...bt("elo", 0.9, "candidate", true), scope: "2023-24" },
  ];

  it("orders candidates by gain, then baselines, from zero and scaled to the best", () => {
    const bars = backtestGainBars(rows);
    expect(bars.map((b) => b.model)).toEqual([
      "elo",
      "poisson",
      "historical",
      "uniform",
    ]);
    expect(bars[0].width).toBe(1);
    expect(bars[1].width).toBeCloseTo(seasonGain(0.949) / seasonGain(0.945));
    expect(bars[3].gain).toBeCloseTo(0);
    expect(bars[3].width).toBe(0);
    expect(bars[0].color).toBe("#7FA2FF");
    expect(bars[2].color).toBe(DRAW_BAR);
  });
});

describe("about helpers", () => {
  it("moves through the timeline tabs with the arrow, Home and End keys", () => {
    expect(timelineKey(0, "ArrowRight", 7)).toBe(1);
    expect(timelineKey(6, "ArrowRight", 7)).toBe(0);
    expect(timelineKey(0, "ArrowLeft", 7)).toBe(6);
    expect(timelineKey(3, "Home", 7)).toBe(0);
    expect(timelineKey(3, "End", 7)).toBe(6);
    expect(timelineKey(3, "Enter", 7)).toBeNull();
    expect(timelineKey(3, "ArrowDown", 7)).toBeNull();
  });

  it("writes round simulation counts in words", () => {
    expect(simsInWords(10000)).toBe("ten thousand");
    expect(simsInWords(12500)).toBe("12,500");
  });
});
