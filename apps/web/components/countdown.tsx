"use client";

import { useEffect, useState } from "react";

import { countdownLabel, countdownParts } from "@/lib/data/home";

const box =
  "flex min-w-16 flex-col items-center rounded-lg border border-line bg-midnight px-3 py-2";

function Box({ value, unit }: { value: string; unit: string }) {
  return (
    <div className={box}>
      <span className="font-score text-[30px] leading-none font-semibold">
        {value}
      </span>
      <span className="mt-1 text-xs text-mist">{unit}</span>
    </div>
  );
}

const pad = (n: number) => String(n).padStart(2, "0");

/**
 * Time to kick-off. The server (and the first client render) shows a static placeholder; ticking
 * starts after mount. Days, hours and minutes move once a minute; seconds appear only in the
 * final hour. The accessible label changes at most once a minute.
 */
export function Countdown({ kickoff }: { kickoff: string }) {
  const target = Date.parse(kickoff);
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      const t = Date.now();
      setNow(t);
      const parts = countdownParts(target - t);
      if (!parts.done) timer = setTimeout(tick, parts.nextTickMs + 20);
    };
    timer = setTimeout(tick, 0);
    return () => clearTimeout(timer);
  }, [target]);

  if (now === null) {
    return (
      <div role="timer" aria-live="off" aria-label="Time to kick-off">
        <div className="flex gap-2" aria-hidden>
          <Box value="–" unit="days" />
          <Box value="–" unit="hrs" />
          <Box value="–" unit="min" />
        </div>
      </div>
    );
  }

  const left = target - now;
  const parts = countdownParts(left);
  if (parts.done) {
    return (
      <p className="font-score text-2xl font-semibold text-floodlight">
        Kicked off — prediction locked
      </p>
    );
  }
  return (
    <div role="timer" aria-live="off" aria-label={countdownLabel(left)}>
      <div className="flex gap-2" aria-hidden>
        <Box value={String(parts.days)} unit="days" />
        <Box value={pad(parts.hours)} unit="hrs" />
        <Box value={pad(parts.minutes)} unit="min" />
        {parts.seconds !== null ? (
          <Box value={pad(parts.seconds)} unit="sec" />
        ) : null}
      </div>
    </div>
  );
}
