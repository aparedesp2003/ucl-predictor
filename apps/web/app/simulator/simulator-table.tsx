"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useState } from "react";

import { ScrollHint } from "@/components/scroll-hint";
import { TeamBadge } from "@/components/team-badge";
import {
  formatSimPct,
  type SortDir,
  sortRows,
  teamName,
} from "@/lib/data/derive";
import type { TitleOdds, TitleRace } from "@/lib/data/types";
import { formatDate } from "@/lib/time";
import { cn } from "@/lib/utils";

type Column = {
  key: string;
  label: string;
  /** Read out in the sort announcement when the label is abbreviated. */
  spoken?: string;
  value: (t: TitleOdds) => number | string;
  firstDir: SortDir;
};

const COLUMNS: Column[] = [
  {
    key: "team",
    label: "Team",
    value: (t) => teamName(t.team),
    firstDir: "asc",
  },
  {
    key: "xpts",
    label: "xPts",
    spoken: "expected points",
    value: (t) => t.expectedPoints,
    firstDir: "desc",
  },
  { key: "top8", label: "Top 8", value: (t) => t.pTop8, firstDir: "desc" },
  {
    key: "playoff",
    label: "Play-offs (9–24)",
    spoken: "play-offs",
    value: (t) => t.pPlayoff,
    firstDir: "desc",
  },
  {
    key: "out",
    label: "Out (25–36)",
    spoken: "out",
    value: (t) => t.pOut,
    firstDir: "desc",
  },
  { key: "r16", label: "Last 16", value: (t) => t.pR16, firstDir: "desc" },
  {
    key: "qf",
    label: "QF",
    spoken: "quarter-finals",
    value: (t) => t.pQf,
    firstDir: "desc",
  },
  {
    key: "sf",
    label: "SF",
    spoken: "semi-finals",
    value: (t) => t.pSf,
    firstDir: "desc",
  },
  { key: "final", label: "Final", value: (t) => t.pFinal, firstDir: "desc" },
  { key: "win", label: "Win", value: (t) => t.pWin, firstDir: "desc" },
];

export function SimulatorTable({ race }: { race: TitleRace }) {
  const [sort, setSort] = useState<{ key: string; dir: SortDir }>({
    key: "win",
    dir: "desc",
  });
  const column = COLUMNS.find((c) => c.key === sort.key) ?? COLUMNS[0];
  const rows = sortRows(race.teams, column.value, sort.dir);
  const maxWin = Math.max(...race.teams.map((t) => t.pWin)) || 1;

  function sortBy(c: Column) {
    setSort((s) =>
      s.key === c.key
        ? { key: c.key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key: c.key, dir: c.firstDir },
    );
  }

  const order =
    column.key === "team"
      ? sort.dir === "asc"
        ? "A to Z"
        : "Z to A"
      : sort.dir === "desc"
        ? "highest first"
        : "lowest first";

  const caption = `${race.nSims.toLocaleString("en-GB")} simulated seasons, results through ${formatDate(race.resultsThrough)}. Ratings plus uncertainty; rules from the 2026/27 regulations.`;

  return (
    <>
      <ScrollHint />
      <div
        className="overflow-x-auto rounded-md border border-line"
        tabIndex={0}
        role="region"
        aria-labelledby="sim-caption"
      >
        <table className="w-full min-w-[56rem] text-sm">
          {/* Visible copy sits below the scroll box so it never scrolls out of view on phones. */}
          <caption id="sim-caption" className="sr-only">
            {caption}
          </caption>
          <thead className="text-xs text-mist">
            <tr className="border-b border-line">
              {COLUMNS.map((c) => {
                const active = c.key === sort.key;
                const Icon = !active
                  ? ArrowUpDown
                  : sort.dir === "asc"
                    ? ArrowUp
                    : ArrowDown;
                return (
                  <th
                    key={c.key}
                    scope="col"
                    aria-sort={
                      active
                        ? sort.dir === "asc"
                          ? "ascending"
                          : "descending"
                        : undefined
                    }
                    className={cn(
                      "p-0 font-normal",
                      c.key === "team"
                        ? "sticky left-0 z-10 bg-night text-left"
                        : "text-right",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => sortBy(c)}
                      className={cn(
                        "inline-flex min-h-11 w-full items-center gap-1 px-3 py-2 whitespace-nowrap hover:text-starlight",
                        c.key === "team" ? "justify-start pl-4" : "justify-end",
                        active && "font-semibold text-starlight",
                      )}
                    >
                      {c.label}
                      <Icon
                        aria-hidden
                        className={cn(
                          "size-3.5 shrink-0",
                          !active && "opacity-50",
                        )}
                      />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.team.id} className="border-b border-rowline">
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-night py-2.5 pr-3 pl-4 text-left font-medium"
                >
                  <span className="flex items-center gap-2 whitespace-nowrap">
                    <TeamBadge team={t.team} size="sm" />
                    {teamName(t.team)}
                  </span>
                </th>
                <td className="px-3 py-2.5 text-right">
                  {t.expectedPoints.toFixed(1)}
                </td>
                <Pct p={t.pTop8} />
                <Pct p={t.pPlayoff} />
                <Pct p={t.pOut} />
                <Pct p={t.pR16} />
                <Pct p={t.pQf} />
                <Pct p={t.pSf} />
                <Pct p={t.pFinal} />
                <td className="px-3 py-2.5 text-right font-semibold">
                  <span className="inline-flex items-center justify-end gap-2">
                    <span
                      aria-hidden
                      className="h-1.5 w-12 overflow-hidden rounded-[1px] bg-rowline"
                    >
                      <span
                        className="block h-full rounded-[1px] bg-floodlight"
                        style={{ width: `${(t.pWin / maxWin) * 100}%` }}
                      />
                    </span>
                    <span className="w-12 font-score text-lg leading-none font-semibold">
                      {formatSimPct(t.pWin)}
                    </span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-sm text-mist" aria-hidden>
        {caption}
      </p>
      <p className="sr-only" aria-live="polite">
        Sorted by {column.spoken ?? column.label}, {order}.
      </p>
    </>
  );
}

function Pct({ p }: { p: number }) {
  return (
    <td className="px-3 py-2.5 text-right text-mist">{formatSimPct(p)}</td>
  );
}
