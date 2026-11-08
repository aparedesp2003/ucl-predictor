"use client";

import { useSyncExternalStore } from "react";

import {
  dateParts,
  formatDayRange,
  formatParts,
  type TimeFormat,
} from "@/lib/time";

const subscribe = () => () => {};

/** The visitor's time zone; "UTC" on the server and during hydration, so markup always matches. */
export function useTimeZone(): string {
  return useSyncExternalStore(
    subscribe,
    () => Intl.DateTimeFormat().resolvedOptions().timeZone,
    () => "UTC",
  );
}

export function LocalTime({
  iso,
  format = "time",
  className,
}: {
  iso: string;
  format?: TimeFormat;
  className?: string;
}) {
  const timeZone = useTimeZone();
  const text = formatParts(dateParts(iso, timeZone), format);
  const showZone =
    timeZone === "UTC" && (format === "time" || format === "dayTime");
  return (
    <time dateTime={iso} className={className}>
      {text}
      {showZone ? " UTC" : null}
    </time>
  );
}

/** First and last kick-off days in the visitor's time zone, e.g. "24–25 Nov". */
export function LocalDateRange({
  first,
  last,
}: {
  first: string;
  last: string;
}) {
  const timeZone = useTimeZone();
  return (
    <span>
      {formatDayRange(dateParts(first, timeZone), dateParts(last, timeZone))}
    </span>
  );
}
