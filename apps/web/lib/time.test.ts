import { describe, expect, it } from "vitest";

import { dateParts, dayKey, formatDayRange } from "./time";

const range = (a: string, b: string, tz = "UTC") =>
  formatDayRange(dateParts(a, tz), dateParts(b, tz));

describe("formatDayRange", () => {
  it("does not repeat the month within one month", () => {
    expect(range("2026-11-24T17:45:00Z", "2026-11-25T20:00:00Z")).toBe(
      "24–25 Nov",
    );
  });

  it("names both months across a month boundary", () => {
    expect(range("2026-11-30T20:00:00Z", "2026-12-01T20:00:00Z")).toBe(
      "30 Nov – 1 Dec",
    );
  });

  it("adds years across a year boundary", () => {
    expect(range("2026-12-31T20:00:00Z", "2027-01-01T20:00:00Z")).toBe(
      "31 Dec 2026 – 1 Jan 2027",
    );
  });

  it("shows a single day once", () => {
    expect(range("2027-01-27T20:00:00Z", "2027-01-27T20:00:00Z")).toBe(
      "27 Jan",
    );
  });

  it("uses the visitor's time zone, not UTC", () => {
    // 20:00 UTC on 25 Nov is already 26 Nov in Tokyo.
    expect(
      range("2026-11-24T20:00:00Z", "2026-11-25T20:00:00Z", "Asia/Tokyo"),
    ).toBe("25–26 Nov");
    expect(dayKey("2026-11-25T20:00:00Z", "Asia/Tokyo")).toBe("2026-11-26");
  });
});
