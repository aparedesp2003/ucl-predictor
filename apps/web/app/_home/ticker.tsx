"use client";

import { Pause, Play } from "lucide-react";
import { useState } from "react";

import { LocalTime } from "@/components/local-time";
import { cn } from "@/lib/utils";

export type TickerItem = {
  id: number;
  kickoff: string;
  homeCode: string;
  awayCode: string;
  homeName: string;
  awayName: string;
  /** Home, draw, away: whole percentages, and whether each is the favoured outcome. */
  outcomes: { pct: string; favoured: boolean }[];
};

function Items({ items, copy }: { items: TickerItem[]; copy?: boolean }) {
  return (
    <ul
      className={cn("flex shrink-0 gap-10 pr-10", copy && "ticker-copy")}
      aria-hidden={copy ? "true" : undefined}
    >
      {items.map((m) => {
        const [home, draw, away] = m.outcomes;
        return (
          <li
            key={m.id}
            className="flex items-center gap-2 font-score text-lg leading-none font-semibold whitespace-nowrap text-silver"
          >
            <span aria-hidden className="flex items-center gap-2">
              <LocalTime
                iso={m.kickoff}
                format="weekday"
                className="text-mist uppercase"
              />
              <span className="text-mist">·</span>
              <span className="text-starlight">{m.homeCode}</span>
              {[home, draw, away].map((o, i) => (
                <span key={i} className="flex items-center gap-2">
                  {i > 0 ? <span className="text-muted">·</span> : null}
                  <span className={o.favoured ? "text-floodlight" : undefined}>
                    {o.pct}
                  </span>
                </span>
              ))}
              <span className="text-starlight">{m.awayCode}</span>
            </span>
            {copy ? null : (
              <span className="sr-only">
                {m.homeName} v {m.awayName}: home win {home.pct}%, draw{" "}
                {draw.pct}%, away win {away.pct}%
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Every fixture of the next matchday, scrolling. Pauses on hover, on focus and with the button;
 * with prefers-reduced-motion it is a static row that scrolls by hand (globals.css).
 */
export function Ticker({ items }: { items: TickerItem[] }) {
  const [paused, setPaused] = useState(false);
  return (
    <section
      aria-label="Next matchday fixtures and predictions"
      className="ticker flex items-center border-b border-line bg-night"
      data-paused={paused ? "" : undefined}
    >
      <div
        tabIndex={0}
        className="ticker-viewport relative min-w-0 flex-1 overflow-hidden py-3"
      >
        <div className="ticker-track flex w-max pl-4 sm:pl-6">
          <Items items={items} />
          <Items items={items} copy />
        </div>
      </div>
      <button
        type="button"
        className="ticker-toggle flex size-11 shrink-0 items-center justify-center border-l border-line text-mist hover:text-starlight"
        aria-pressed={paused}
        aria-label="Pause ticker"
        onClick={() => setPaused((p) => !p)}
      >
        {paused ? (
          <Play aria-hidden className="size-4" />
        ) : (
          <Pause aria-hidden className="size-4" />
        )}
      </button>
    </section>
  );
}
