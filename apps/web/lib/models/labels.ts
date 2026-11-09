// The one map from engine model ids to visitor-facing labels.
//
// Live pages (Home, the Accuracy headline and live table) show only the models predicting this
// season, so the shrunk Poisson is just "Poisson" there. The backtest compares every candidate,
// so the Poisson variants keep distinct labels (see BACKTEST_VARIANTS_NOTE).

export type LabelContext = "live" | "backtest";

const LABELS: Record<string, { backtest: string; live?: string }> = {
  elo: { backtest: "Elo" },
  blend: { backtest: "Blend" },
  poisson_shrink: { backtest: "Poisson (shrunk)", live: "Poisson" },
  poisson_cal: { backtest: "Poisson (calibrated)" },
  poisson: { backtest: "Poisson" },
  uniform: { backtest: "Guessing" },
  historical: { backtest: "Base rates" },
};

export function modelLabel(model: string, context: LabelContext): string {
  const labels = LABELS[model];
  if (!labels) return model;
  return (context === "live" && labels.live) || labels.backtest;
}

// Matches engine.evaluate.candidates: s scales the Poisson rating slope (PoissonParams.shrunk), T is
// temperature scaling (evaluate.calibrate.temperature_scale); both fitted on validation seasons.
export const BACKTEST_VARIANTS_NOTE =
  "Poisson (shrunk) scales down how much the rating gap moves expected goals, pulling predictions toward an even match; Poisson (calibrated) applies temperature scaling to the three probabilities; Blend averages Elo and Poisson (calibrated). Both adjustments are fitted on validation seasons only.";
