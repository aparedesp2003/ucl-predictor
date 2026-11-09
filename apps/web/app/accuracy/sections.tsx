import { connection } from "next/server";

import { EmptyState } from "@/components/empty-state";
import { GrowOnMount } from "@/components/grow-on-mount";
import { LocalTime } from "@/components/local-time";
import {
  getBacktest,
  getCurrentSeason,
  getScoredPredictions,
} from "@/lib/data/accuracy";
import { formatPct, teamName } from "@/lib/data/derive";
import { getSeasonMatches } from "@/lib/data/matches";
import { safely } from "@/lib/data/safe";
import {
  backtestGainBars,
  callNote,
  gainHeadline,
  hitSummary,
  landedCalls,
  matchdayTiles,
  type MatchdayTile,
  modelLanes,
  seasonGain,
  stripColor,
  UPSET,
  upsets,
} from "@/lib/data/scorecard";
import { getScoreboard } from "@/lib/data/scoreboard";
import type { ScoredPrediction } from "@/lib/data/types";
import { BACKTEST_VARIANTS_NOTE, modelLabel } from "@/lib/models/labels";
import { cn } from "@/lib/utils";

import { CalibrationChart } from "./calibration-chart";
import { PredictionList } from "./prediction-list";

const kicker = "text-sm font-medium tracking-wide text-floodlight uppercase";
const h2 = "font-display text-3xl font-semibold";
const PROMISE =
  "Every prediction is locked before kick-off, then marked once the final whistle blows. No edits, no hindsight.";

// Every section reads at request time: connection() keeps database reads out of the build.
async function loadLive() {
  await connection();
  const season = await safely(getCurrentSeason);
  if (!season) return { season, scores: [], scored: [] as ScoredPrediction[] };
  const [scores, scored] = await Promise.all([
    safely(() => getScoreboard(season)),
    safely(() => getScoredPredictions(season)),
  ]);
  return { season, scores: scores ?? [], scored: scored ?? [] };
}

// --- a) Hero ------------------------------------------------------------------------------------

export async function Hero() {
  const { season, scores, scored } = await loadLive();
  const primary = scores.find((s) => s.isPrimary);
  const label = `Season scorecard${season ? ` · ${season}` : ""}`;

  if (!primary || primary.n === 0 || !scored.length) {
    return (
      <div>
        <p className={kicker}>{label}</p>
        <h1 className="mt-3 font-display text-4xl font-semibold sm:text-[44px]">
          No matches scored yet
        </h1>
        <p className="mt-4 max-w-[60ch] text-lg text-mist">{PROMISE}</p>
        <div className="mt-6 max-w-xl">
          <EmptyState title="The scorecard starts after the first predicted match">
            Each match counts once it has been played, scored against the
            prediction that was locked before kick-off.
          </EmptyState>
        </div>
      </div>
    );
  }

  const head = gainHeadline(seasonGain(primary.logLoss));
  const { hits, n, share } = hitSummary(scored);
  return (
    <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_auto]">
      <div>
        <p className={kicker}>{label}</p>
        <h1 className="mt-3">
          <span className="block font-score text-[84px] leading-[0.9] font-bold md:text-[148px]">
            {head.value}
          </span>
          <span className="mt-2 block font-display text-3xl font-semibold sm:text-[44px]">
            {head.word} than guessing
          </span>
        </h1>
        <p className="mt-5 max-w-[60ch] text-lg text-mist">{PROMISE}</p>
      </div>
      <div className="flex items-center gap-6">
        <ScoreRing share={share} />
        <p>
          <span className="block font-score text-[52px] leading-none font-bold">
            {hits} / {n}
          </span>
          <span className="mt-1 block text-mist">favourites came through</span>
        </p>
      </div>
    </div>
  );
}

function ScoreRing({ share }: { share: number }) {
  return (
    <GrowOnMount className="relative size-36 shrink-0">
      <svg viewBox="0 0 128 128" aria-hidden className="size-full -rotate-90">
        <circle
          cx="64"
          cy="64"
          r="50"
          fill="none"
          stroke="#141C46"
          strokeWidth="14"
        />
        <circle
          cx="64"
          cy="64"
          r="50"
          fill="none"
          className="grow-ring stroke-floodlight"
          strokeWidth="14"
          strokeLinecap="round"
          pathLength={100}
          strokeDasharray="100 100"
          strokeDashoffset={100 - share * 100}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-score text-3xl font-bold">
        {formatPct(share)}
      </span>
    </GrowOnMount>
  );
}

// --- b) Model lanes -----------------------------------------------------------------------------

export async function ModelLanes() {
  const { scores } = await loadLive();
  const lanes = modelLanes(scores);
  if (!lanes.length) {
    return (
      <EmptyState title="No live scores yet">
        Each model gets a lane after its first predicted match is played.
      </EmptyState>
    );
  }
  return (
    <GrowOnMount>
      <ul className="space-y-3">
        {lanes.map((l) => (
          <li
            key={l.key}
            className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_4.5rem] items-center gap-3 sm:grid-cols-[minmax(0,12rem)_minmax(0,1fr)_5rem]"
          >
            <span className="min-w-0">
              <span
                className={cn("block truncate", l.emphasis && "font-semibold")}
              >
                {l.label}
              </span>
              {l.tag ? (
                <span className="text-xs text-floodlight">{l.tag}</span>
              ) : null}
            </span>
            <span
              aria-hidden
              className="block h-10 overflow-hidden rounded-[10px] border border-line bg-midnight"
            >
              <span
                className="grow-bar block h-full rounded-[9px] ring-1 ring-white/18 ring-inset"
                style={{ width: `${l.width * 100}%`, backgroundColor: l.color }}
              />
            </span>
            <span className="text-right font-score text-[30px] leading-none font-semibold">
              {l.logLoss.toFixed(3)}
            </span>
          </li>
        ))}
      </ul>
    </GrowOnMount>
  );
}

// --- c) Matchday tiles --------------------------------------------------------------------------

export async function MatchdayTiles() {
  await connection();
  const [{ scored }, matches] = await Promise.all([
    loadLive(),
    safely(getSeasonMatches),
  ]);
  const tiles = matchdayTiles(matches ?? [], scored);
  return (
    <ol className="grid grid-cols-[repeat(auto-fit,minmax(7.5rem,1fr))] gap-3">
      {tiles.map((t) => (
        <Tile key={t.matchday} tile={t} />
      ))}
    </ol>
  );
}

function Tile({ tile: t }: { tile: MatchdayTile }) {
  const base = "flex min-h-32 flex-col rounded-xl p-4";
  const title = (
    <span className="text-xs tracking-wide uppercase">
      Matchday {t.matchday}
    </span>
  );
  switch (t.state) {
    case "scored":
      return (
        <li className={cn(base, "bg-floodlight text-night")}>
          {title}
          <span
            aria-hidden
            className="mt-auto font-score text-4xl leading-none font-bold"
          >
            {t.hits}/{t.n}
          </span>
          <span aria-hidden className="mt-1 text-sm">
            Log loss {t.logLoss.toFixed(3)}
          </span>
          <span className="sr-only">
            : {t.hits} of {t.n} favourites came through, log loss{" "}
            {t.logLoss.toFixed(3)}
          </span>
        </li>
      );
    case "beforeLaunch":
      return (
        <li
          className={cn(base, "border-2 border-dashed border-line text-mist")}
        >
          {title}
          <span
            aria-hidden
            className="mt-auto font-score text-4xl leading-none font-bold"
          >
            —
          </span>
          <span className="mt-1 text-sm">
            <span className="sr-only">: played </span>Before launch
            <span className="sr-only">, no predictions to score</span>
          </span>
        </li>
      );
    case "next":
      return (
        <li className={cn(base, "border-2 border-floodlight")}>
          <span className="text-floodlight">{title}</span>
          <span className="mt-auto font-score text-3xl leading-none font-bold">
            <span className="sr-only">: next up, first kick-off </span>
            <LocalTime iso={t.firstKickoff} format="date" />
          </span>
          <span className="mt-1 text-sm text-mist">
            {t.locked} locked in
            <span className="sr-only"> before kick-off</span>
          </span>
        </li>
      );
    default:
      return (
        <li className={cn(base, "border border-line text-muted")}>
          {title}
          <span className="mt-auto text-sm">
            <span className="sr-only">: </span>Upcoming
          </span>
        </li>
      );
  }
}

// --- d) Calls that landed / upsets --------------------------------------------------------------

export async function LandedAndUpsets() {
  const { scored } = await loadLive();
  if (!scored.length) return null;
  const landed = landedCalls(scored);
  const shocks = upsets(scored);
  return (
    <div className="grid gap-10 lg:grid-cols-2">
      <section aria-labelledby="landed">
        <h2 id="landed" className={h2}>
          Calls that landed
        </h2>
        <p className="mt-1 mb-5 text-sm text-mist">
          The hits the model was surest about.
        </p>
        <CallCards rows={landed} upset={false} />
      </section>
      <section aria-labelledby="upsets">
        <h2 id="upsets" className={h2}>
          The upsets
        </h2>
        <p className="mt-1 mb-5 text-sm text-mist">
          What happened when the model gave it the least chance.
        </p>
        {shocks.length ? (
          <CallCards rows={shocks} upset />
        ) : (
          <EmptyState title="No upsets yet">
            Every favourite has come through so far.
          </EmptyState>
        )}
      </section>
    </div>
  );
}

function CallCards({
  rows,
  upset,
}: {
  rows: ScoredPrediction[];
  upset: boolean;
}) {
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li
          key={r.matchId}
          className={cn(
            "flex overflow-hidden rounded-xl border bg-midnight",
            upset ? "border-[#F5A35C]/40" : "border-line",
          )}
        >
          <span
            aria-hidden
            className="w-2.5 shrink-0"
            style={{ backgroundColor: stripColor(r) }}
          />
          <div className="flex min-w-0 flex-1 items-center justify-between gap-4 p-4">
            <div className="min-w-0">
              <p className="truncate font-medium">
                {teamName(r.home)} v {teamName(r.away)}
              </p>
              <p
                className="mt-1 text-sm"
                style={upset ? { color: UPSET } : undefined}
              >
                <span className={upset ? undefined : "text-mist"}>
                  {callNote(r)}
                </span>
              </p>
            </div>
            <p className="shrink-0 font-score text-[40px] leading-none font-bold">
              <span className="sr-only">Score </span>
              {r.homeGoals}–{r.awayGoals}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

// --- e) Every prediction ------------------------------------------------------------------------

export async function Predictions() {
  const { scored } = await loadLive();
  if (!scored.length) {
    return (
      <EmptyState title="No finished matches with a prediction yet">
        Each match is listed here once it has been played, with the prediction
        that was locked before kick-off.
      </EmptyState>
    );
  }
  const newest = [...scored].sort(
    (a, b) => b.kickoff.localeCompare(a.kickoff) || b.matchId - a.matchId,
  );
  return <PredictionList rows={newest} />;
}

// --- f) Backtest --------------------------------------------------------------------------------

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
  const bars = backtestGainBars(backtest.rows);
  const n = backtest.rows.find((r) => r.scope === "overall")?.n ?? 0;
  const seasons = [
    ...new Set(
      backtest.rows.filter((r) => r.scope !== "overall").map((r) => r.scope),
    ),
  ].sort();
  const cell = (model: string, season: string) =>
    backtest.rows.find((r) => r.model === model && r.scope === season);
  const th = "px-3 py-2 text-right font-normal";
  const td = "px-3 py-2 text-right";

  return (
    <div className="grid gap-12 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <section aria-labelledby="backtest">
        <p className={kicker}>Before the season</p>
        <h2 id="backtest" className={cn(h2, "mt-2")}>
          Tested on{" "}
          <span className="font-score text-[1.3em] font-bold">
            {n.toLocaleString("en-GB")}
          </span>{" "}
          past matches
        </h2>
        <p className="mt-2 mb-6 max-w-[60ch] text-sm text-mist">
          Before launch, every candidate predicted five past seasons (
          {seasons[0]} to {seasons[seasons.length - 1]}) it had never been tuned
          on. Each bar is its gain over guessing a third each.
        </p>
        <GrowOnMount>
          <ul className="space-y-3">
            {bars.map((b) => (
              <li
                key={b.model}
                className="grid grid-cols-[minmax(0,9.5rem)_minmax(0,1fr)_4.5rem] items-center gap-3"
              >
                <span
                  className={cn(
                    "min-w-0 text-sm",
                    b.isPrimary
                      ? "font-semibold"
                      : b.role === "baseline"
                        ? "text-mist"
                        : undefined,
                  )}
                >
                  <span className="block truncate">{b.label}</span>
                  {b.isPrimary ? (
                    <span className="text-xs font-normal text-floodlight">
                      main model
                    </span>
                  ) : b.role === "baseline" ? (
                    <span className="text-xs">baseline</span>
                  ) : null}
                </span>
                <span
                  aria-hidden
                  className="block h-7 overflow-hidden rounded-lg bg-midnight"
                >
                  <span
                    className="grow-bar block h-full rounded-lg ring-1 ring-white/18 ring-inset"
                    style={{
                      width: `${b.width * 100}%`,
                      backgroundColor: b.color,
                    }}
                  />
                </span>
                <span
                  className={cn(
                    "text-right font-score text-2xl leading-none font-semibold",
                    b.isPrimary && "text-floodlight",
                  )}
                >
                  {formatPct(b.gain, 1)}
                </span>
              </li>
            ))}
          </ul>
        </GrowOnMount>
        <p className="mt-5 max-w-[60ch] text-xs text-mist">
          {BACKTEST_VARIANTS_NOTE}
        </p>

        <details className="mt-2 text-sm">
          <summary className="cursor-pointer py-2 text-floodlight">
            Log loss and RPS by test season
          </summary>
          <div
            className="mt-3 overflow-x-auto"
            tabIndex={0}
            role="region"
            aria-label="Backtest log loss and RPS by season"
          >
            <table className="w-full min-w-[40rem]">
              <caption className="sr-only">
                Backtest log loss per test season and overall RPS; lower is
                better
              </caption>
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
                  <th scope="col" className={th}>
                    RPS
                  </th>
                </tr>
              </thead>
              <tbody>
                {bars.map((b) => (
                  <tr
                    key={b.model}
                    className={cn(
                      "border-b border-rowline",
                      b.role === "baseline" && "text-mist",
                    )}
                  >
                    <th scope="row" className="py-2 pr-3 text-left font-medium">
                      {b.label}
                    </th>
                    {seasons.map((s) => (
                      <td key={s} className={td}>
                        {cell(b.model, s)?.logLoss.toFixed(3) ?? "–"}
                      </td>
                    ))}
                    <td className={td}>
                      {cell(b.model, "overall")?.rps.toFixed(3) ?? "–"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      {backtest.calibration ? (
        <section aria-labelledby="calibration">
          <h2 id="calibration" className={h2}>
            Do the percentages hold up?
          </h2>
          <p className="mt-2 mb-6 max-w-[60ch] text-sm text-mist">
            When the {modelLabel(backtest.calibration.model, "backtest")} model
            gave a side, say, a 40% chance, did it win about 40% of the time?
            Dots on the dashed line are spot on; bigger dots hold more matches.
          </p>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-1">
            <CalibrationChart
              title="Home win"
              model={modelLabel(backtest.calibration.model, "backtest")}
              bins={backtest.calibration.home}
            />
            <CalibrationChart
              title="Away win"
              model={modelLabel(backtest.calibration.model, "backtest")}
              bins={backtest.calibration.away}
            />
          </div>
        </section>
      ) : null}
    </div>
  );
}
