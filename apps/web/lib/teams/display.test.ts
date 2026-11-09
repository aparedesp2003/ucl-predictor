import { describe, expect, it } from "vitest";

import {
  badgeColors,
  contrastRatio,
  NEUTRAL_COLORS,
  teamColors,
} from "./colors";
import { displayCode, displayName, TEAM_DISPLAY } from "./display";

// The 2026-27 league-phase teams exactly as football-data stores them (fd_team_id, tla, short_name,
// name), copied from the database.
const CURRENT: [number, string, string, string][] = [
  [100, "ROM", "Roma", "AS Roma"],
  [57, "ARS", "Arsenal", "Arsenal FC"],
  [58, "AVL", "Aston Villa", "Aston Villa FC"],
  [5, "FCB", "Bayern", "Bayern München"],
  [4, "BVB", "Dortmund", "Borussia Dortmund"],
  [78, "ATL", "Atleti", "Club Atlético de Madrid"],
  [851, "BRU", "Club Brugge", "Club Brugge KV"],
  [7397, "COM", "Como 1907", "Como 1907"],
  [81, "FCB", "Barça", "FC Barcelona"],
  [108, "INT", "Inter", "FC Internazionale Milano"],
  [503, "FCP", "Porto", "FC Porto"],
  [5721, "FK", "Bodø/Glimt", "FK Bodø/Glimt"],
  [1887, "SHD", "Shaktar", "FK Shakhtar Donetsk"],
  [613, "FEN", "Fenerbahçe", "Fenerbahçe"],
  [675, "FEY", "Feyenoord", "Feyenoord Rotterdam"],
  [610, "GAL", "Galatasaray", "Galatasaray"],
  [2016, "LIN", "LASK", "LASK Linz"],
  [521, "LIL", "Lille", "Lille OSC"],
  [64, "LIV", "Liverpool", "Liverpool FC"],
  [65, "MCI", "Man City", "Manchester City"],
  [66, "MUN", "Man United", "Manchester United"],
  [1899, "AEK", "PAE AEK", "PAE AEK"],
  [674, "PSV", "PSV", "PSV"],
  [524, "PSG", "PSG", "Paris Saint-Germain"],
  [721, "RBL", "RB Leipzig", "RB Leipzig"],
  [546, "RCL", "RC Lens", "Racing Club de Lens"],
  [90, "BET", "Real Betis", "Real Betis Balompié"],
  [86, "RMA", "Real Madrid", "Real Madrid"],
  [113, "NAP", "Napoli", "SSC Napoli"],
  [10233, "SAB", "Sabah FK", "Sabah FK"],
  [930, "SLP", "Slavia Praha", "Slavia Praha"],
  [498, "SPO", "Sporting CP", "Sporting Clube de Portugal"],
  [10, "VFB", "Stuttgart", "VfB Stuttgart"],
  [5720, "VIK", "Viking", "Viking FK"],
  [94, "VIL", "Villarreal", "Villarreal CF"],
  [7509, "SBA", "Sl. Bratislava", "ŠK Slovan Bratislava"],
];

const teams = CURRENT.map(([fdId, tla, shortName, name]) => ({
  fdId,
  tla,
  shortName,
  name,
}));
const byFd = (fdId: number) => teams.find((t) => t.fdId === fdId)!;

describe("team display map", () => {
  it("covers every current team", () => {
    expect(teams).toHaveLength(36);
    for (const t of teams) expect(TEAM_DISPLAY[t.fdId], t.name).toBeDefined();
  });

  it("gives every current team a unique three-letter code", () => {
    const codes = teams.map(displayCode);
    for (const code of codes) expect(code).toMatch(/^[A-Z]{3}$/);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it("fixes the known names", () => {
    const names: [number, string][] = [
      [1887, "Shakhtar"],
      [1899, "AEK"],
      [546, "Lens"],
      [7397, "Como"],
      [7509, "Slovan Bratislava"],
    ];
    for (const [fdId, name] of names)
      expect(displayName(byFd(fdId))).toBe(name);
  });

  it("fixes the known badge codes", () => {
    const codes: [number, string][] = [
      [81, "BAR"], // Barcelona
      [5, "FCB"], // Bayern keeps FCB
      [5721, "BOD"],
      [2016, "LAS"],
      [930, "SLA"],
      [1887, "SHA"],
      [498, "SCP"],
      [503, "POR"],
      [7509, "SLO"],
    ];
    for (const [fdId, code] of codes)
      expect(displayCode(byFd(fdId))).toBe(code);
  });

  it("still resolves club colours from the stored TLA", () => {
    for (const t of teams)
      expect(teamColors(t), t.name).not.toBe(NEUTRAL_COLORS);
    expect(teamColors(byFd(81)).primary).not.toBe(teamColors(byFd(5)).primary);
  });

  it("falls back to the stored short name and TLA", () => {
    const unknown = { fdId: 1, tla: "XYZ", shortName: "Short", name: "Full" };
    expect(displayName(unknown)).toBe("Short");
    expect(displayCode(unknown)).toBe("XYZ");
    const bare = {
      fdId: null,
      tla: null,
      shortName: null,
      name: "Some Team Name",
    };
    expect(displayName(bare)).toBe("Some Team Name");
    expect(displayCode(bare)).toBe("STN");
  });

  it("keeps badge text at 4.5:1 or more on the primary and the clash colour", () => {
    for (const t of teams) {
      for (const bg of [undefined, teamColors(t).secondary]) {
        const { background, text } = badgeColors(t, bg);
        expect(contrastRatio(background, text), t.name).toBeGreaterThanOrEqual(
          4.5,
        );
      }
    }
  });
});
