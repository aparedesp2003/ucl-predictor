import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ARENA_MARK_SMALL_SVG, ARENA_MARK_SVG, NINETY_PATH } from "./marks";

describe("brand marks", () => {
  it("never depend on a web font where none is loaded", () => {
    const icon = readFileSync(
      path.join(__dirname, "..", "..", "app", "icon.svg"),
      "utf8",
    );
    for (const svg of [icon, ARENA_MARK_SVG, ARENA_MARK_SMALL_SVG]) {
      expect(svg).not.toMatch(/<text|font-family/);
      expect(svg).toMatch(
        /^<svg xmlns="http:\/\/www.w3.org\/2000\/svg" viewBox="0 0 120 100">/,
      );
    }
  });

  it("use the small mark, outlined, as the favicon", () => {
    const icon = readFileSync(
      path.join(__dirname, "..", "..", "app", "icon.svg"),
      "utf8",
    );
    expect(icon.trim()).toBe(ARENA_MARK_SMALL_SVG);
    expect(icon).toContain(NINETY_PATH);
  });
});
