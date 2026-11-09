"use client";

import { useId, useRef, useState } from "react";

import { timelineKey } from "@/lib/data/scorecard";
import { cn } from "@/lib/utils";

export type TimelineStep = { minute: string; title: string; text: string };

/**
 * The method as a match, 0' to 90': an ARIA tabs widget (roving tabindex; Left/Right/Home/End).
 * The step row scrolls inside its own box on narrow screens.
 */
export function Timeline({ steps }: { steps: TimelineStep[] }) {
  const base = useId();
  const [active, setActive] = useState(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const tabId = (i: number) => `${base}-tab-${i}`;
  const panelId = `${base}-panel`;
  const step = steps[active];
  const fill = steps.length > 1 ? (active / (steps.length - 1)) * 100 : 0;

  const onKeyDown = (e: React.KeyboardEvent) => {
    const next = timelineKey(active, e.key, steps.length);
    if (next === null) return;
    e.preventDefault();
    setActive(next);
    tabs.current[next]?.focus();
  };

  return (
    <div>
      <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <div className="relative min-w-[38rem] pt-1">
          <div
            aria-hidden
            className="absolute top-[23px] right-[calc(100%/14)] left-[calc(100%/14)] h-1.5 rounded-full bg-line"
          >
            <div
              className="h-full rounded-full bg-floodlight transition-[width] duration-300 motion-reduce:transition-none"
              style={{ width: `${fill}%` }}
            />
          </div>
          <div
            role="tablist"
            aria-label="From kick-off to final whistle"
            onKeyDown={onKeyDown}
            className="relative grid"
            style={{
              gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))`,
            }}
          >
            {steps.map((s, i) => {
              const state =
                i < active ? "past" : i === active ? "active" : "future";
              return (
                <button
                  key={s.minute}
                  ref={(el) => {
                    tabs.current[i] = el;
                  }}
                  id={tabId(i)}
                  type="button"
                  role="tab"
                  aria-selected={i === active}
                  aria-controls={panelId}
                  tabIndex={i === active ? 0 : -1}
                  onClick={() => setActive(i)}
                  className="group flex flex-col items-center gap-2 rounded-lg pb-1"
                >
                  <span
                    className={cn(
                      "flex size-11 items-center justify-center rounded-full border-2 font-score text-base font-bold",
                      state === "past" &&
                        "border-floodlight bg-[#1E3A8A] text-starlight",
                      state === "active" &&
                        "border-floodlight bg-floodlight text-night",
                      state === "future" &&
                        "border-line bg-night text-mist group-hover:border-floodlight",
                    )}
                  >
                    {s.minute}
                  </span>{" "}
                  <span
                    className={cn(
                      "text-xs",
                      i === active
                        ? "font-semibold text-starlight"
                        : "text-mist",
                    )}
                  >
                    {s.title}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div
        id={panelId}
        role="tabpanel"
        aria-labelledby={tabId(active)}
        tabIndex={0}
        className="mt-8 grid items-center gap-x-10 gap-y-2 rounded-[20px] border border-line bg-midnight p-6 sm:grid-cols-[auto_minmax(0,1fr)] sm:p-8"
      >
        <p
          aria-hidden
          className="font-score text-[72px] leading-none font-bold text-floodlight md:text-[112px]"
        >
          {step.minute}
        </p>
        <div>
          <h3 className="font-display text-2xl font-semibold">{step.title}</h3>
          <p className="mt-2 max-w-[60ch] text-lg text-mist">{step.text}</p>
        </div>
      </div>
    </div>
  );
}
