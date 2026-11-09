"use client";

import Link from "next/link";
import { useState } from "react";

import { GrowOnMount } from "@/components/grow-on-mount";
import { TeamBadge } from "@/components/team-badge";
import { teamName } from "@/lib/data/derive";
import {
  formatRacePct,
  RACE_METRICS,
  raceColors,
  raceTop,
  type RaceMetric,
} from "@/lib/data/home";
import type { TitleOdds } from "@/lib/data/types";
import { cn } from "@/lib/utils";

/** The top eight by the chosen round, re-sorted when the tab changes; bars scaled to the leader. */
export function Race({
  teams,
  caption,
}: {
  teams: TitleOdds[];
  caption: string;
}) {
  const [metric, setMetric] = useState<RaceMetric>("pWin");
  const current = RACE_METRICS.find((m) => m.key === metric)!;
  const top = raceTop(teams, metric);
  const colors = raceColors(top.map((t) => t.team));
  const leader = top[0]?.[metric] || 1;

  return (
    <>
      <div
        role="group"
        aria-label="Show the chance of"
        className="mb-5 inline-flex flex-wrap gap-1 rounded-xl border border-line bg-midnight p-1"
      >
        {RACE_METRICS.map((m) => (
          <button
            key={m.key}
            type="button"
            aria-pressed={metric === m.key}
            onClick={() => setMetric(m.key)}
            className={cn(
              "min-h-11 rounded-lg px-4 text-sm font-medium",
              metric === m.key
                ? "bg-floodlight text-night"
                : "text-mist hover:text-starlight",
            )}
          >
            {m.label}
          </button>
        ))}
      </div>
      <p className="sr-only" aria-live="polite">
        Sorted by {current.long}
      </p>

      <GrowOnMount>
        <ol className="space-y-2">
          {top.map((t, i) => (
            <li
              key={t.team.id}
              className="grid grid-cols-[minmax(0,150px)_minmax(0,1fr)_4.5rem] items-center gap-3"
            >
              <span className="flex min-w-0 items-center gap-2 font-medium">
                <TeamBadge team={t.team} size="sm" />
                <span className="truncate">{teamName(t.team)}</span>
              </span>
              <span
                aria-hidden
                className="block h-[34px] overflow-hidden rounded-[10px] border border-line bg-midnight"
              >
                <span
                  className="grow-bar block h-full rounded-[9px] ring-1 ring-white/18 ring-inset"
                  style={{
                    width: `${(t[metric] / leader) * 100}%`,
                    backgroundColor: colors[i],
                  }}
                />
              </span>
              <span className="text-right font-score text-[28px] leading-none font-semibold">
                {formatRacePct(t[metric])}
              </span>
            </li>
          ))}
        </ol>
      </GrowOnMount>

      <p className="mt-4 text-sm text-mist">
        {caption} ·{" "}
        <Link
          href="/simulator"
          className="text-floodlight underline decoration-floodlight/40 underline-offset-2 hover:decoration-floodlight"
        >
          Every club in the simulator
        </Link>
      </p>
    </>
  );
}
