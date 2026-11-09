import { describe, expect, it } from "vitest";

import {
  contrastRatio,
  SURFACE_NIGHT,
  SURFACE_TRACK,
  TEAM_COLORS,
} from "@/lib/teams/colors";

import {
  boldestCalls,
  closestCall,
  countdownLabel,
  countdownParts,
  favouriteSide,
  DRAW_BAR,
  formatRacePct,
  heroBarColors,
  lastCompletedMatchday,
  matchdayFixtures,
  nextMatchday,
  raceColors,
  raceTop,
  reportCard,
  tickerOutcomes,
} from "./home";
import type { MatchRow, ScoredPrediction, TeamRef, TitleOdds } from "./types";

const team = (
  tla: string,
  name = tla,
  fdId: number | null = null,
): TeamRef => ({
  id: tla.charCodeAt(0) * 100 + tla.charCodeAt(1),
  fdId,
  name,
  shortName: name,
  tla,
});

const NOW = Date.parse("2026-11-20T12:00:00Z");
let nextId = 1;

function match(
  over: Partial<MatchRow> & { p?: [number, number, number] | null } = {},
): MatchRow {
  const { p = [0.4, 0.3, 0.3], ...rest } = over;
  return {
    id: nextId++,
    season: "2026-27",
    stage: "LEAGUE_PHASE",
    matchday: 5,
    leg: null,
    kickoff: "2026-11-24T20:00:00.000Z",
    status: "SCHEDULED",
    homeGoals: null,
    awayGoals: null,
    home: team("PSG"),
    away: team("ARS"),
    prediction: p
      ? {
          pHome: p[0],
          pDraw: p[1],
          pAway: p[2],
          model: "elo",
          predictedAt: "2026-11-19T06:15:00.000Z",
        }
      : null,
    ...rest,
  };
}

describe("nextMatchday", () => {
  it("is the lowest matchday with a scheduled match", () => {
    const ms = [
      match({ matchday: 4, status: "FINISHED" }),
      match({ matchday: 5 }),
      match({ matchday: 6 }),
    ];
    expect(nextMatchday(ms)).toBe(5);
  });

  it("is null once every league match is played", () => {
    expect(
      nextMatchday([match({ matchday: 8, status: "FINISHED" })]),
    ).toBeNull();
    expect(nextMatchday([])).toBeNull();
  });
});

describe("matchdayFixtures", () => {
  it("keeps one matchday in kick-off order", () => {
    const late = match({ kickoff: "2026-11-25T20:00:00.000Z" });
    const early = match({ kickoff: "2026-11-24T17:45:00.000Z" });
    const other = match({ matchday: 6 });
    expect(matchdayFixtures([late, other, early], 5)).toEqual([early, late]);
  });
});

describe("closestCall", () => {
  it("picks the smallest top probability", () => {
    const lopsided = match({ p: [0.7, 0.2, 0.1] });
    const close = match({ p: [0.36, 0.3, 0.34] });
    const middling = match({ p: [0.45, 0.3, 0.25] });
    expect(closestCall([lopsided, close, middling], NOW)?.id).toBe(close.id);
  });

  it("counts the draw as a possible top outcome", () => {
    const drawish = match({ p: [0.3, 0.42, 0.28] }); // top 0.42
    const split = match({ p: [0.4, 0.2, 0.4] }); // top 0.40
    expect(closestCall([drawish, split], NOW)?.id).toBe(split.id);
  });

  it("breaks ties by the earliest kick-off", () => {
    const later = match({
      p: [0.38, 0.3, 0.32],
      kickoff: "2026-11-25T20:00:00.000Z",
    });
    const earlier = match({
      p: [0.32, 0.3, 0.38],
      kickoff: "2026-11-24T17:45:00.000Z",
    });
    expect(closestCall([later, earlier], NOW)?.id).toBe(earlier.id);
  });

  it("skips unpredicted and kicked-off fixtures", () => {
    const unpredicted = match({ p: null });
    const started = match({
      p: [0.34, 0.33, 0.33],
      kickoff: "2026-11-20T11:00:00.000Z",
    });
    const open = match({ p: [0.6, 0.2, 0.2] });
    expect(closestCall([unpredicted, started, open], NOW)?.id).toBe(open.id);
  });

  it("is null when there is nothing left to call", () => {
    expect(closestCall([], NOW)).toBeNull();
    expect(closestCall([match({ status: "FINISHED" })], NOW)).toBeNull();
  });
});

describe("boldestCalls", () => {
  it("sorts by the stronger side and keeps six", () => {
    const ps: [number, number, number][] = [
      [0.5, 0.3, 0.2],
      [0.1, 0.2, 0.7], // away 0.7
      [0.8, 0.1, 0.1],
      [0.3, 0.45, 0.25], // the draw does not count: 0.3
      [0.55, 0.25, 0.2],
      [0.6, 0.2, 0.2],
      [0.2, 0.15, 0.65],
    ];
    const ms = ps.map((p) => match({ p }));
    const got = boldestCalls(ms).map((m) =>
      Math.max(m.prediction.pHome, m.prediction.pAway),
    );
    expect(got).toEqual([0.8, 0.7, 0.65, 0.6, 0.55, 0.5]);
  });

  it("names the favoured side between the two teams", () => {
    expect(favouriteSide({ pHome: 0.2, pAway: 0.5 })).toBe("A");
    expect(favouriteSide({ pHome: 0.4, pAway: 0.4 })).toBe("H");
  });
});

describe("tickerOutcomes", () => {
  it("flags the single favoured outcome, the draw included", () => {
    expect(
      tickerOutcomes({ pHome: 0.3, pDraw: 0.4, pAway: 0.3 }).map(
        (o) => o.favoured,
      ),
    ).toEqual([false, true, false]);
  });
});

describe("race for the trophy", () => {
  const odds = (
    tla: string,
    pR16: number,
    pSf: number,
    pFinal: number,
    pWin: number,
  ): TitleOdds => ({
    team: team(tla),
    pTop8: 0,
    pPlayoff: 0,
    pOut: 0,
    pR16,
    pQf: 0,
    pSf,
    pFinal,
    pWin,
    expectedPoints: 0,
  });
  const teams = [
    odds("PSG", 0.9, 0.5, 0.35, 0.3),
    odds("ARS", 0.95, 0.4, 0.25, 0.2),
    odds("LIV", 0.8, 0.45, 0.3, 0.25),
    ...Array.from({ length: 8 }, (_, i) =>
      odds(`T${i}`, 0.5 - i * 0.01, 0.1, 0.05, 0.01),
    ),
  ];

  it("re-sorts the top eight by the chosen metric", () => {
    expect(
      raceTop(teams, "pWin")
        .map((t) => t.team.tla)
        .slice(0, 3),
    ).toEqual(["PSG", "LIV", "ARS"]);
    expect(
      raceTop(teams, "pR16")
        .map((t) => t.team.tla)
        .slice(0, 3),
    ).toEqual(["ARS", "PSG", "LIV"]);
    expect(
      raceTop(teams, "pSf")
        .map((t) => t.team.tla)
        .slice(0, 3),
    ).toEqual(["PSG", "LIV", "ARS"]);
    expect(raceTop(teams, "pWin")).toHaveLength(8);
  });

  it("breaks ties by win chance", () => {
    const tied = [odds("ARS", 0.9, 0, 0, 0.2), odds("PSG", 0.9, 0, 0, 0.3)];
    expect(raceTop(tied, "pR16").map((t) => t.team.tla)).toEqual([
      "PSG",
      "ARS",
    ]);
  });

  it("switches a bar to its secondary when it clashes with the bar above", () => {
    // Arsenal red over Liverpool red: Liverpool takes its secondary; Dortmund yellow is distinct.
    expect(raceColors([team("ARS"), team("LIV"), team("BVB")])).toEqual([
      TEAM_COLORS.ARS.primary,
      TEAM_COLORS.LIV.secondary,
      TEAM_COLORS.BVB.primary,
    ]);
  });

  it("formats race percentages", () => {
    expect(formatRacePct(0.996)).toBe(">99%");
    expect(formatRacePct(0.995)).toBe(">99%");
    expect(formatRacePct(0.994)).toBe("99%");
    expect(formatRacePct(0.0099)).toBe("<1%");
    expect(formatRacePct(0)).toBe("<1%");
    expect(formatRacePct(0.01)).toBe("1.0%");
    expect(formatRacePct(0.0432)).toBe("4.3%");
    expect(formatRacePct(0.0996)).toBe("10%");
    expect(formatRacePct(0.302)).toBe("30%");
  });
});

describe("report card", () => {
  const scored = (
    matchday: number,
    hit: boolean,
    logLoss: number,
    kickoff = "2026-11-04T20:00:00.000Z",
  ): ScoredPrediction => ({
    matchId: nextId++,
    model: "elo",
    stage: "LEAGUE_PHASE",
    matchday,
    kickoff,
    home: team("VIK", "Viking"),
    away: team("SAB", "Sabah"),
    homeGoals: 4,
    awayGoals: 1,
    outcome: "H",
    predicted: hit ? "H" : "A",
    pHome: 0.5,
    pDraw: 0.25,
    pAway: 0.25,
    logLoss,
    rps: 0.1,
    hit,
  });

  it("finds the latest fully played, scored matchday", () => {
    const matches = [
      match({ matchday: 3, status: "FINISHED" }),
      match({ matchday: 4, status: "FINISHED" }),
      match({ matchday: 4, status: "FINISHED" }),
      match({ matchday: 5, status: "FINISHED" }),
      match({ matchday: 5 }), // matchday 5 is not finished yet
    ];
    const rows = [
      scored(3, true, 0.5),
      scored(4, true, 0.5),
      scored(5, false, 1),
    ];
    expect(lastCompletedMatchday(matches, rows)).toBe(4);
    expect(lastCompletedMatchday(matches, [])).toBeNull();
  });

  it("counts hits and compares the log loss with guessing", () => {
    const rows = [
      scored(4, true, 0.5, "2026-11-04T20:00:00.000Z"),
      scored(4, false, 1.5, "2026-11-03T17:45:00.000Z"),
      scored(4, true, 0.4, "2026-11-04T17:45:00.000Z"),
      scored(3, false, 2),
    ];
    const card = reportCard(rows, 4)!;
    expect(card).toMatchObject({ matchday: 4, hits: 2, n: 3 });
    expect(card.logLoss).toBeCloseTo(0.8);
    expect(card.gain).toBeCloseTo((Math.log(3) - 0.8) / Math.log(3));
    expect(card.dots.map((d) => d.hit)).toEqual([false, true, true]); // kick-off order
    expect(card.dots[0].label).toBe("Viking 4–1 Sabah, upset");
    expect(card.dots[1].label).toBe("Viking 4–1 Sabah, favourite won");
  });

  it("reports a negative gain when the model did worse than guessing", () => {
    expect(reportCard([scored(4, false, 1.5)], 4)!.gain).toBeLessThan(0);
  });

  it("is null for a matchday without scores", () => {
    expect(reportCard([scored(3, true, 0.5)], 4)).toBeNull();
  });
});

describe("countdown", () => {
  const MIN = 60_000;

  it("moves once a minute until the final hour", () => {
    const p = countdownParts(61 * MIN + 30_000);
    expect(p).toMatchObject({
      done: false,
      days: 0,
      hours: 1,
      minutes: 1,
      seconds: null,
    });
    if (!p.done) expect(p.nextTickMs).toBe(30_000);
  });

  it("shows seconds and ticks every second in the final hour", () => {
    const p = countdownParts(59 * MIN + 12_400);
    expect(p).toMatchObject({
      done: false,
      hours: 0,
      minutes: 59,
      seconds: 12,
    });
    if (!p.done) expect(p.nextTickMs).toBe(400);
  });

  it("switches to seconds exactly at one hour", () => {
    expect(countdownParts(60 * MIN)).toMatchObject({ seconds: 0 });
    expect(countdownParts(60 * MIN + 1)).toMatchObject({ seconds: null });
  });

  it("splits days, hours and minutes", () => {
    expect(countdownParts((3 * 24 * 60 + 4 * 60 + 12) * MIN)).toMatchObject({
      days: 3,
      hours: 4,
      minutes: 12,
      seconds: null,
    });
  });

  it("is done at kick-off", () => {
    expect(countdownParts(0)).toEqual({ done: true });
    expect(countdownParts(-5)).toEqual({ done: true });
  });

  it("labels at minute precision", () => {
    expect(countdownLabel((3 * 24 * 60 + 4 * 60 + 12) * MIN + 59_000)).toBe(
      "3 days 4 hours 12 minutes to kick-off",
    );
    expect(countdownLabel(59 * MIN + 30_000)).toBe("59 minutes to kick-off");
    expect(countdownLabel(61 * MIN)).toBe("1 hour 1 minute to kick-off");
    expect(countdownLabel(0)).toBe("Kicked off, prediction locked");
  });
});

describe("bar contrast (WCAG 1.4.11)", () => {
  it("draws Fenerbahçe in yellow in the hero bar", () => {
    // Shakhtar orange vs Fenerbahçe navy do not clash, but navy is too dark on the night card.
    expect(
      heroBarColors(team("SHD", "Shakhtar"), team("FEN", "Fenerbahçe")),
    ).toEqual([TEAM_COLORS.SHD.primary, DRAW_BAR, "#FFED00"]);
  });

  it("keeps the draw segment at 3:1 on the card", () => {
    expect(contrastRatio(DRAW_BAR, SURFACE_NIGHT)).toBeGreaterThanOrEqual(3);
  });

  it("draws Man City in sky blue in the race, even below a clashing colour", () => {
    // Under Liverpool's teal the clash rule picks City's navy secondary, which fails on the track;
    // the passing sky-blue primary wins over the clash.
    const colors = raceColors([team("LIV"), team("MCI")]);
    expect(colors[1]).toBe("#6CABDD");
  });

  it("gives every race bar 3:1 against the track", () => {
    const tlas = Object.keys(TEAM_COLORS).filter((t) => t !== "BAR");
    for (const c of raceColors(tlas.map((t) => team(t))))
      expect(contrastRatio(c, SURFACE_TRACK)).toBeGreaterThanOrEqual(3);
  });
});
