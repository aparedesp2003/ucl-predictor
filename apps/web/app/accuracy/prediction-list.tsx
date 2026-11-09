"use client";

import { useId, useState } from "react";

import { LocalTime } from "@/components/local-time";
import { TeamBadge } from "@/components/team-badge";
import { roundLabel, teamName } from "@/lib/data/derive";
import {
  ALL_ROUNDS,
  backedLabel,
  filterPredictions,
  predictionCounts,
  type ResultFilter,
  UPSET,
} from "@/lib/data/scorecard";
import type { ScoredPrediction } from "@/lib/data/types";
import { clashColors } from "@/lib/teams/colors";
import { cn } from "@/lib/utils";

const FILTERS: { key: ResultFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "hits", label: "Hits" },
  { key: "upsets", label: "Upsets" },
];

/** The primary model's scored predictions (newest first), filterable by result and round. */
export function PredictionList({ rows }: { rows: ScoredPrediction[] }) {
  const selectId = useId();
  const [result, setResult] = useState<ResultFilter>("all");
  const [round, setRound] = useState(ALL_ROUNDS);
  // Rounds in playing order; rows arrive newest first.
  const rounds = [...new Set([...rows].reverse().map(roundLabel))];
  const counts = predictionCounts(rows, round);
  const shown = filterPredictions(rows, { result, round });

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-x-5 gap-y-3">
        <div
          role="group"
          aria-label="Show predictions"
          className="flex flex-wrap gap-2"
        >
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              aria-pressed={result === f.key}
              onClick={() => setResult(f.key)}
              className={cn(
                "min-h-11 rounded-full border px-4 text-sm font-medium",
                result === f.key
                  ? "border-floodlight bg-floodlight text-night"
                  : "border-line text-mist hover:text-starlight",
              )}
            >
              {f.label}{" "}
              <span className="font-score text-base font-semibold">
                {counts[f.key]}
              </span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor={selectId} className="text-sm text-mist">
            Round
          </label>
          <select
            id={selectId}
            value={round}
            onChange={(e) => setRound(e.target.value)}
            className="min-h-11 rounded-sm border border-line bg-midnight px-3 text-sm text-starlight"
          >
            <option value={ALL_ROUNDS}>All rounds</option>
            {rounds.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <p className="text-sm text-mist" aria-live="polite">
          Showing {shown.length} of {counts.all}
        </p>
      </div>

      {shown.length ? (
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(min(260px,100%),1fr))] gap-3">
          {shown.map((r) => (
            <Card key={r.matchId} row={r} />
          ))}
        </ul>
      ) : (
        <p className="text-mist">No predictions match this filter.</p>
      )}
    </div>
  );
}

function Card({ row: r }: { row: ScoredPrediction }) {
  const colors = clashColors(r.home, r.away);
  return (
    <li className="flex flex-col rounded-xl border border-line bg-midnight p-4">
      <div className="flex items-center justify-between gap-2 text-xs text-mist">
        <span>
          {roundLabel(r)} · <LocalTime iso={r.kickoff} format="date" />
        </span>
        {r.hit ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-floodlight px-2.5 py-0.5 font-semibold text-night">
            <span aria-hidden>✓</span> Hit
          </span>
        ) : (
          <span
            className="inline-flex items-center gap-1 rounded-full border-2 px-2 py-px font-semibold"
            style={{ borderColor: UPSET, color: UPSET }}
          >
            <span aria-hidden>✗</span> Upset
          </span>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="min-w-0 space-y-1.5 font-medium">
          <p className="flex items-center gap-2">
            <TeamBadge team={r.home} size="sm" color={colors.home} />
            <span className="truncate">{teamName(r.home)}</span>
            <span className="sr-only">versus</span>
          </p>
          <p className="flex items-center gap-2">
            <TeamBadge team={r.away} size="sm" color={colors.away} />
            <span className="truncate">{teamName(r.away)}</span>
          </p>
        </div>
        <p className="shrink-0 font-score text-4xl leading-none font-bold">
          <span className="sr-only">Score </span>
          {r.homeGoals}–{r.awayGoals}
        </p>
      </div>
      <div className="mt-3 flex items-baseline justify-between gap-2 border-t border-rowline pt-3 text-sm">
        <span>{backedLabel(r)}</span>
        <span className="text-xs text-mist">
          Log loss {r.logLoss.toFixed(3)}
        </span>
      </div>
    </li>
  );
}
