// Date formatting that renders identically on the server and in every browser: the parts come
// from Intl (or getUTC* for UTC), the wording is assembled here, never by the runtime's locale data.

const WEEKDAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export type DateParts = {
  year: number;
  month: number; // 1-12
  day: number;
  weekday: number; // 0 = Sunday
  hour: number;
  minute: number;
};

export function dateParts(iso: string, timeZone = "UTC"): DateParts {
  const d = new Date(iso);
  if (timeZone === "UTC") {
    return {
      year: d.getUTCFullYear(),
      month: d.getUTCMonth() + 1,
      day: d.getUTCDate(),
      weekday: d.getUTCDay(),
      hour: d.getUTCHours(),
      minute: d.getUTCMinutes(),
    };
  }
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    hourCycle: "h23",
  }).formatToParts(d);
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((p) => p.type === type)?.value);
  const [year, month, day] = [get("year"), get("month"), get("day")];
  return {
    year,
    month,
    day,
    weekday: new Date(Date.UTC(year, month - 1, day)).getUTCDay(),
    hour: get("hour") % 24,
    minute: get("minute"),
  };
}

const pad = (n: number) => String(n).padStart(2, "0");

export type TimeFormat = "time" | "date" | "day" | "dayTime";

export function formatParts(p: DateParts, format: TimeFormat): string {
  const time = `${pad(p.hour)}:${pad(p.minute)}`;
  const month = MONTHS[p.month - 1];
  switch (format) {
    case "time":
      return time;
    case "date":
      return `${p.day} ${month.slice(0, 3)}`;
    case "day":
      return `${WEEKDAYS[p.weekday]} ${p.day} ${month}`;
    case "dayTime":
      return `${WEEKDAYS[p.weekday].slice(0, 3)} ${p.day} ${month.slice(0, 3)}, ${time}`;
  }
}

/** YYYY-MM-DD of the instant in the given zone, for grouping by day. */
export function dayKey(iso: string, timeZone = "UTC"): string {
  const p = dateParts(iso, timeZone);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
}

/** "4 Nov 2026" for a plain YYYY-MM-DD date (no time zone involved). */
export function formatDate(ymd: string): string {
  const [year, month, day] = ymd.split("-").map(Number);
  return `${day} ${MONTHS[month - 1].slice(0, 3)} ${year}`;
}
