"use client";

import { Check, X } from "lucide-react";
import { useId, useState } from "react";

import { LocalTime } from "@/components/local-time";
import { ScrollHint } from "@/components/scroll-hint";
import { TeamBadge } from "@/components/team-badge";
import { formatPct, roundLabel, teamName } from "@/lib/data/derive";
import type { ScoredPrediction } from "@/lib/data/types";
import { clashColors } from "@/lib/teams/colors";
import { cn } from "@/lib/utils";

const ALL = "all";

/** The primary model's scored predictions (newest first), filterable by round. */
export function PredictionList({ rows }: { rows: ScoredPrediction[] }) {
  const selectId = useId();
  const [round, setRound] = useState(ALL);
  // Rounds in playing order; rows arrive newest first.
  const rounds = [...new Set([...rows].reverse().map(roundLabel))];
  const shown =
    round === ALL ? rows : rows.filter((r) => roundLabel(r) === round);
  const hits = shown.filter((r) => r.hit).length;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <label htmlFor={selectId} className="text-sm text-mist">
          Show
        </label>
        <select
          id={selectId}
          value={round}
          onChange={(e) => setRound(e.target.value)}
          className="min-h-11 rounded-sm border border-line bg-midnight px-3 text-sm text-starlight"
        >
          <option value={ALL}>All rounds</option>
          {rounds.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <p className="text-sm text-mist" aria-live="polite">
          {hits} of {shown.length} called right
        </p>
      </div>

      <ScrollHint />
      <div
        className="overflow-x-auto"
        tabIndex={0}
        role="region"
        aria-label="Every scored prediction"
      >
        <table className="w-full min-w-[44rem] text-sm">
          <thead className="text-left text-xs text-mist">
            <tr className="border-b border-line">
              <th scope="col" className="w-20 py-2 font-normal">
                Date
              </th>
              <th scope="col" className="py-2 font-normal">
                Match
              </th>
              <th scope="col" className="px-3 py-2 text-right font-normal">
                Score
              </th>
              <th scope="col" className="px-3 py-2 font-normal">
                Predicted
              </th>
              <th scope="col" className="px-3 py-2 font-normal">
                Result
              </th>
              <th scope="col" className="py-2 pl-3 text-right font-normal">
                Log loss
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <Row key={r.matchId} row={r} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Row({ row: r }: { row: ScoredPrediction }) {
  const colors = clashColors(r.home, r.away);
  const pick =
    r.predicted === "H"
      ? { label: teamName(r.home), p: r.pHome }
      : r.predicted === "A"
        ? { label: teamName(r.away), p: r.pAway }
        : { label: "Draw", p: r.pDraw };

  return (
    <tr className="border-b border-rowline">
      <td className="py-3 text-mist">
        <LocalTime iso={r.kickoff} format="date" />
      </td>
      <th scope="row" className="py-3 text-left font-medium">
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="flex items-center gap-2">
            <TeamBadge team={r.home} size="sm" color={colors.home} />
            {teamName(r.home)}
          </span>
          <span className="text-mist" aria-hidden>
            v
          </span>
          <span className="sr-only">versus</span>
          <span className="flex items-center gap-2">
            <TeamBadge team={r.away} size="sm" color={colors.away} />
            {teamName(r.away)}
          </span>
        </span>
      </th>
      <td className="px-3 py-3 text-right font-semibold whitespace-nowrap">
        {r.homeGoals}–{r.awayGoals}
      </td>
      <td className="px-3 py-3 whitespace-nowrap">
        {pick.label} <span className="text-mist">{formatPct(pick.p)}</span>
      </td>
      <td className="px-3 py-3">
        <span
          className={cn(
            "inline-flex items-center gap-1 text-xs",
            r.hit ? "text-starlight" : "text-mist",
          )}
        >
          {r.hit ? (
            <Check
              aria-hidden
              className="size-3.5 text-floodlight"
              strokeWidth={2.5}
            />
          ) : (
            <X aria-hidden className="size-3.5" strokeWidth={2.5} />
          )}
          {r.hit ? "Hit" : "Miss"}
        </span>
      </td>
      <td className="py-3 pl-3 text-right">{r.logLoss.toFixed(3)}</td>
    </tr>
  );
}
