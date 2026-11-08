import { connection } from "next/server";

import { EmptyState } from "@/components/empty-state";
import {
  getBacktest,
  getCurrentSeason,
  getScoredPredictions,
} from "@/lib/data/accuracy";
import {
  formatPct,
  improvementOverGuessing,
  modelName,
} from "@/lib/data/derive";
import { safely } from "@/lib/data/safe";
import { getScoreboard } from "@/lib/data/scoreboard";
import type { BacktestRow } from "@/lib/data/types";
import { cn } from "@/lib/utils";

import { CalibrationChart } from "./calibration-chart";
import { PredictionList } from "./prediction-list";

// Every section reads at request time: connection() keeps database reads out of the build.
async function loadLive() {
  await connection();
  const season = await safely(getCurrentSeason);
  const scores = season
    ? ((await safely(() => getScoreboard(season))) ?? [])
    : [];
  return { season, scores: [...scores].sort((a, b) => a.logLoss - b.logLoss) };
}

const plural = (n: number, word: string) =>
  `${n.toLocaleString("en-GB")} ${word}${n === 1 ? "" : "es"}`;

export async function Headline() {
  const { scores } = await loadLive();
  const primary = scores.find((s) => s.isPrimary);
  if (!primary) {
    return (
      <>
        <h1 className="mt-2 font-display text-4xl font-semibold">
          No matches scored yet
        </h1>
        <p className="mt-3 max-w-[70ch] text-mist">
          Predictions lock before kick-off and are scored after full time. The
          first numbers appear here once a predicted match has finished.
        </p>
      </>
    );
  }
  const gain = improvementOverGuessing(primary);
  return (
    <>
      <h1 className="mt-2 font-display text-4xl leading-tight font-semibold sm:text-5xl">
        {formatPct(Math.abs(gain), 1)} {gain >= 0 ? "better" : "worse"} than
        guessing
      </h1>
      <p className="mt-3 max-w-[70ch] text-mist">
        The {modelName(primary.model)} model&apos;s log loss is{" "}
        {primary.logLoss.toFixed(3)}, against{" "}
        {primary.uniformLogLoss.toFixed(3)} for a third on each outcome, over{" "}
        {plural(primary.n, "match")} this season.
      </p>
    </>
  );
}

const th = "px-3 py-2 text-right font-normal";
const td = "px-3 py-2 text-right";

export async function LiveTable() {
  const { scores } = await loadLive();
  if (!scores.length) {
    return (
      <EmptyState title="Nothing to score yet">
        Each model appears here after its first predicted match is played.
      </EmptyState>
    );
  }
  const base = scores.find((s) => s.isPrimary) ?? scores[0];

  return (
    <div
      className="overflow-x-auto"
      tabIndex={0}
      role="region"
      aria-label="Live scores per model"
    >
      <table className="w-full min-w-[32rem] text-sm">
        <caption className="sr-only">
          Live scores per model this season; lower log loss and RPS are better
        </caption>
        <thead className="text-xs text-mist">
          <tr className="border-b border-line">
            <th scope="col" className="py-2 pr-3 text-left font-normal">
              Model
            </th>
            <th scope="col" className={th}>
              Matches
            </th>
            <th scope="col" className={th}>
              Log loss
            </th>
            <th scope="col" className={th}>
              RPS
            </th>
            <th scope="col" className={th}>
              Accuracy
            </th>
          </tr>
        </thead>
        <tbody>
          {scores.map((s) => (
            <tr key={s.model} className="border-b border-rowline">
              <th scope="row" className="py-2 pr-3 text-left font-medium">
                {modelName(s.model)}
                {s.isPrimary ? <PrimaryTag /> : null}
              </th>
              <td className={td}>{s.n}</td>
              <td className={cn(td, "font-semibold")}>
                {s.logLoss.toFixed(3)}
              </td>
              <td className={td}>{s.rps.toFixed(3)}</td>
              <td className={td}>{formatPct(s.accuracy)}</td>
            </tr>
          ))}
          <tr className="border-b border-rowline text-mist">
            <th scope="row" className="py-2 pr-3 text-left font-medium">
              Guessing{" "}
              <span className="text-xs font-normal">(a third each)</span>
            </th>
            <td className={td}>{base.n}</td>
            <td className={td}>{base.uniformLogLoss.toFixed(3)}</td>
            <td className={td}>{base.uniformRps.toFixed(3)}</td>
            <td className={td}>{formatPct(base.uniformAccuracy)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function PrimaryTag() {
  return <span className="ml-2 text-xs font-normal text-mist">primary</span>;
}

export async function Predictions() {
  const { season } = await loadLive();
  const rows = season ? await safely(() => getScoredPredictions(season)) : [];
  if (rows === null) {
    return (
      <EmptyState title="Predictions are unavailable right now">
        Please try again later.
      </EmptyState>
    );
  }
  if (!rows.length) {
    return (
      <EmptyState title="No finished matches with a prediction yet">
        Each match is listed here once it has been played, with the prediction
        that was locked before kick-off.
      </EmptyState>
    );
  }
  return <PredictionList rows={rows} />;
}

export async function BacktestSection() {
  await connection();
  const backtest = await safely(getBacktest);
  if (!backtest?.rows.length) {
    return (
      <EmptyState title="No backtest results yet">
        They appear once the models have been backtested.
      </EmptyState>
    );
  }
  const overall = backtest.rows.filter((r) => r.scope === "overall");
  const ordered = [
    ...overall
      .filter((r) => r.role === "candidate")
      .sort((a, b) => a.logLoss - b.logLoss),
    ...overall
      .filter((r) => r.role === "baseline")
      .sort((a, b) => a.logLoss - b.logLoss),
  ];
  const seasons = [
    ...new Set(
      backtest.rows.filter((r) => r.scope !== "overall").map((r) => r.scope),
    ),
  ].sort();
  const cell = (model: string, season: string) =>
    backtest.rows.find((r) => r.model === model && r.scope === season);

  return (
    <div className="space-y-12">
      <div>
        <div
          className="overflow-x-auto"
          tabIndex={0}
          role="region"
          aria-label="Backtest results per model"
        >
          <table className="w-full min-w-[36rem] text-sm">
            <caption className="caption-bottom pt-3 text-left text-sm text-mist">
              All {ordered[0]?.n.toLocaleString("en-GB")} main-competition
              matches of the five test seasons. Baselines need no model:
              guessing gives a third to each outcome, base rates use how often
              home wins, draws and away wins happened in earlier seasons.
            </caption>
            <thead className="text-xs text-mist">
              <tr className="border-b border-line">
                <th scope="col" className="py-2 pr-3 text-left font-normal">
                  Model
                </th>
                <th scope="col" className={th}>
                  Log loss
                </th>
                <th scope="col" className={th}>
                  RPS
                </th>
                <th scope="col" className={th}>
                  Brier
                </th>
                <th scope="col" className={th}>
                  Accuracy
                </th>
                <th scope="col" className={th}>
                  Matches
                </th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((r) => (
                <BacktestRowView key={r.model} row={r} />
              ))}
            </tbody>
          </table>
        </div>

        <details className="mt-4 text-sm">
          <summary className="cursor-pointer text-floodlight">
            Log loss by test season
          </summary>
          <div
            className="mt-3 overflow-x-auto"
            tabIndex={0}
            role="region"
            aria-label="Backtest log loss by season"
          >
            <table className="w-full min-w-[36rem]">
              <thead className="text-xs text-mist">
                <tr className="border-b border-line">
                  <th scope="col" className="py-2 pr-3 text-left font-normal">
                    Model
                  </th>
                  {seasons.map((s) => (
                    <th key={s} scope="col" className={th}>
                      {s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ordered.map((r) => (
                  <tr
                    key={r.model}
                    className={cn(
                      "border-b border-rowline",
                      r.role === "baseline" && "text-mist",
                    )}
                  >
                    <th scope="row" className="py-2 pr-3 text-left font-medium">
                      {modelName(r.model)}
                    </th>
                    {seasons.map((s) => (
                      <td key={s} className={td}>
                        {cell(r.model, s)?.logLoss.toFixed(3) ?? "–"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      {backtest.calibration ? (
        <div>
          <h3 className="font-display text-xl font-semibold">Calibration</h3>
          <p className="mt-1 mb-5 max-w-[70ch] text-sm text-mist">
            When the {modelName(backtest.calibration.model)} model said a side
            had, say, a 40% chance, did that side win about 40% of the time?
            Each dot is a group of test matches by predicted chance; dots on the
            diagonal are perfectly calibrated, and bigger dots hold more
            matches.
          </p>
          <div className="grid gap-8 sm:grid-cols-2">
            <CalibrationChart
              title="Home win"
              model={modelName(backtest.calibration.model)}
              bins={backtest.calibration.home}
            />
            <CalibrationChart
              title="Away win"
              model={modelName(backtest.calibration.model)}
              bins={backtest.calibration.away}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function BacktestRowView({ row: r }: { row: BacktestRow }) {
  const baseline = r.role === "baseline";
  return (
    <tr className={cn("border-b border-rowline", baseline && "text-mist")}>
      <th scope="row" className="py-2 pr-3 text-left font-medium">
        {modelName(r.model)}
        {r.isPrimary ? <PrimaryTag /> : null}
        {baseline ? (
          <span className="ml-2 text-xs font-normal">baseline</span>
        ) : null}
      </th>
      <td className={cn(td, !baseline && "font-semibold")}>
        {r.logLoss.toFixed(3)}
      </td>
      <td className={td}>{r.rps.toFixed(3)}</td>
      <td className={td}>{r.brier.toFixed(3)}</td>
      <td className={td}>{formatPct(r.accuracy)}</td>
      <td className={td}>{r.n.toLocaleString("en-GB")}</td>
    </tr>
  );
}
