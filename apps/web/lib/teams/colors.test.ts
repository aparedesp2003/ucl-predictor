import { describe, expect, it } from "vitest";

import {
  clashColors,
  colorKey,
  NEUTRAL_COLORS,
  rgbDistance,
  TEAM_COLORS,
  teamColors,
} from "./colors";

const team = (tla: string | null, name = "Team") => ({ tla, name });

describe("teamColors", () => {
  it("returns the colours for a known TLA", () => {
    expect(teamColors(team("PSG"))).toEqual({
      primary: "#004170",
      onPrimary: "#FFFFFF",
      secondary: "#DA291C",
    });
  });

  it("falls back to neutral for unknown or missing TLAs", () => {
    expect(teamColors(team("XYZ"))).toBe(NEUTRAL_COLORS);
    expect(teamColors(team(null))).toBe(NEUTRAL_COLORS);
  });

  it("tells FC Barcelona and Bayern apart although both are FCB", () => {
    expect(colorKey(team("FCB", "FC Barcelona"))).toBe("BAR");
    expect(colorKey(team("FCB", "Bayern München"))).toBe("FCB");
    expect(teamColors(team("FCB", "FC Barcelona")).primary).toBe("#A50044");
  });

  it("uses valid six-digit hex colours", () => {
    for (const colors of Object.values(TEAM_COLORS)) {
      for (const hex of Object.values(colors))
        expect(hex).toMatch(/^#[0-9A-F]{6}$/);
    }
  });
});

describe("clashColors", () => {
  it("measures RGB distance", () => {
    expect(rgbDistance("#000000", "#000000")).toBe(0);
    expect(rgbDistance("#FF0000", "#000000")).toBe(255);
  });

  it("switches the away side to its secondary when the primaries clash", () => {
    // Arsenal red vs Liverpool red
    expect(clashColors(team("ARS"), team("LIV"))).toEqual({
      home: "#EF0107",
      away: "#00B2A9",
    });
  });

  it("keeps both primaries when they are distinct", () => {
    expect(clashColors(team("PSG"), team("BVB"))).toEqual({
      home: "#004170",
      away: "#FDE100",
    });
  });

  it("works with unknown teams on both sides", () => {
    expect(clashColors(team(null), team("NOPE"))).toEqual({
      home: NEUTRAL_COLORS.primary,
      away: NEUTRAL_COLORS.secondary,
    });
  });
});
