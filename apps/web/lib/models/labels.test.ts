import { describe, expect, it } from "vitest";

import { modelLabel } from "./labels";

describe("modelLabel", () => {
  it("calls the shrunk Poisson just Poisson on live pages", () => {
    expect(modelLabel("poisson_shrink", "live")).toBe("Poisson");
    expect(modelLabel("elo", "live")).toBe("Elo");
  });

  it("keeps the backtest labels distinct", () => {
    const ids = [
      "elo",
      "blend",
      "poisson_shrink",
      "poisson_cal",
      "poisson",
      "uniform",
      "historical",
    ];
    const labels = ids.map((m) => modelLabel(m, "backtest"));
    expect(labels).toEqual([
      "Elo",
      "Blend",
      "Poisson (shrunk)",
      "Poisson (calibrated)",
      "Poisson",
      "Guessing",
      "Base rates",
    ]);
    expect(new Set(labels).size).toBe(ids.length);
  });

  it("falls back to the model id", () => {
    expect(modelLabel("mystery", "live")).toBe("mystery");
  });
});
