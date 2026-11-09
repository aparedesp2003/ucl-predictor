import { describe, expect, it } from "vitest";

import {
  BAR_FALLBACK,
  barColor,
  clashColors,
  colorKey,
  contrastRatio,
  NEUTRAL_COLORS,
  rgbDistance,
  SURFACE_NIGHT,
  SURFACE_TRACK,
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

describe("barColor (WCAG 1.4.11, 3:1 against the surface)", () => {
  it("keeps a colour that already reaches 3:1", () => {
    expect(barColor(team("BVB"), "#FDE100", SURFACE_TRACK)).toBe("#FDE100");
  });

  it("switches to the team's other colour when the chosen one fails", () => {
    // PSG navy fails on the track; its red passes.
    expect(barColor(team("PSG"), "#004170", SURFACE_TRACK)).toBe("#DA291C");
    // Man City's navy secondary fails; the sky-blue primary passes.
    expect(barColor(team("MCI"), "#1C2C5B", SURFACE_TRACK)).toBe("#6CABDD");
  });

  it("falls back to silver when both colours fail", () => {
    const barca = team("FCB", "FC Barcelona");
    expect(barColor(barca, teamColors(barca).primary, SURFACE_NIGHT)).toBe(
      BAR_FALLBACK,
    );
  });

  it("gives every club a passing bar on both surfaces", () => {
    for (const [tla, c] of Object.entries(TEAM_COLORS)) {
      const t = tla === "BAR" ? team("FCB", "FC Barcelona") : team(tla);
      for (const surface of [SURFACE_NIGHT, SURFACE_TRACK]) {
        for (const chosen of [c.primary, c.secondary]) {
          expect(
            contrastRatio(barColor(t, chosen, surface), surface),
            tla,
          ).toBeGreaterThanOrEqual(3);
        }
      }
    }
  });
});
