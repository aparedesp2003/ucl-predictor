"use client";

import { Check, X } from "lucide-react";

import { LocalTime, useTimeZone } from "@/components/local-time";
import { ProbabilityBar } from "@/components/probability-bar";
import { TeamBadge } from "@/components/team-badge";
import { favoured, formatPct, isHit, teamName } from "@/lib/data/derive";
import type { MatchRow } from "@/lib/data/types";
import { clashColors } from "@/lib/teams/colors";
import { dateParts, dayKey, formatParts } from "@/lib/time";
import { cn } from "@/lib/utils";

/** Matches grouped by the visitor's local kick-off day (UTC until the browser takes over). */
export function MatchdayTable({ rows }: { rows: MatchRow[] }) {
  const timeZone = useTimeZone();
  const groups = new Map<string, MatchRow[]>();
  for (const row of rows) {
    const key = dayKey(row.kickoff, timeZone);
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }

  return (
    <div
      className="overflow-x-auto"
      tabIndex={0}
      role="region"
      aria-label="Matches table"
    >
      <table className="w-full min-w-[46rem] text-sm">
        <thead className="text-left text-xs text-mist">
          <tr className="border-b border-line">
            <th scope="col" className="w-24 py-2 font-normal">
              Kickoff
            </th>
            <th scope="col" className="py-2 font-normal">
              Home
            </th>
            <th scope="col" className="w-56 px-4 py-2 font-normal">
              Home · Draw · Away
            </th>
            <th scope="col" className="py-2 font-normal">
              Away
            </th>
            <th scope="col" className="w-32 py-2 text-right font-normal">
              Result
            </th>
          </tr>
        </thead>
        {[...groups].map(([key, matches]) => (
          <tbody key={key}>
            <tr>
              <th
                scope="colgroup"
                colSpan={5}
                className="pt-6 pb-2 text-left font-display text-base font-medium text-silver"
              >
                {formatParts(dateParts(matches[0].kickoff, timeZone), "day")}
              </th>
            </tr>
            {matches.map((m) => (
              <MatchRowView key={m.id} match={m} />
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}

function MatchRowView({ match: m }: { match: MatchRow }) {
  const colors = clashColors(m.home, m.away);
  const p = m.prediction;
  const pick = p ? favoured(p) : null;
  const tone = (side: "H" | "D" | "A") =>
    pick === side ? "font-semibold text-starlight" : "text-mist";

  return (
    <tr className="border-t border-rowline">
      <td className="py-3 text-mist">
        <LocalTime iso={m.kickoff} />
      </td>
      <th scope="row" className="py-3 text-left font-medium">
        <span className="flex items-center gap-2">
          <TeamBadge team={m.home} size="sm" color={colors.home} />
          {teamName(m.home)}
        </span>
      </th>
      <td className="px-4 py-3">
        {p ? (
          <div>
            <ProbabilityBar
              pHome={p.pHome}
              pDraw={p.pDraw}
              pAway={p.pAway}
              homeName={teamName(m.home)}
              awayName={teamName(m.away)}
              homeColor={colors.home}
              awayColor={colors.away}
            />
            <div className="mt-1.5 flex justify-between text-xs" aria-hidden>
              <span className={tone("H")}>{formatPct(p.pHome)}</span>
              <span className={tone("D")}>{formatPct(p.pDraw)}</span>
              <span className={tone("A")}>{formatPct(p.pAway)}</span>
            </div>
          </div>
        ) : (
          <span className="text-muted">No prediction</span>
        )}
      </td>
      <td className="py-3 font-medium">
        <span className="flex items-center gap-2">
          <TeamBadge team={m.away} size="sm" color={colors.away} />
          {teamName(m.away)}
        </span>
      </td>
      <td className="py-3 text-right">
        <Result match={m} />
      </td>
    </tr>
  );
}

function Result({ match: m }: { match: MatchRow }) {
  if (m.status === "POSTPONED" || m.status === "CANCELLED") {
    return (
      <span className="text-mist">
        {m.status === "POSTPONED" ? "Postponed" : "Cancelled"}
      </span>
    );
  }
  if (m.homeGoals === null || m.awayGoals === null || m.status !== "FINISHED") {
    return (
      <span className="text-muted">
        <span aria-hidden>–</span>
        <span className="sr-only">Not played yet</span>
      </span>
    );
  }
  const hit = isHit(m);
  return (
    <span className="inline-flex items-center justify-end gap-3">
      <span className="font-semibold">
        {m.homeGoals}–{m.awayGoals}
      </span>
      {hit === null ? null : (
        <span
          className={cn(
            "inline-flex items-center gap-1 text-xs",
            hit ? "text-starlight" : "text-mist",
          )}
        >
          {hit ? (
            <Check
              aria-hidden
              className="size-3.5 text-floodlight"
              strokeWidth={2.5}
            />
          ) : (
            <X aria-hidden className="size-3.5" strokeWidth={2.5} />
          )}
          {hit ? "Hit" : "Miss"}
        </span>
      )}
    </span>
  );
}
