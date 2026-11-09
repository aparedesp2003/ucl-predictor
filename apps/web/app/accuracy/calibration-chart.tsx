import { EmptyState } from "@/components/empty-state";
import { formatPct } from "@/lib/data/derive";
import type { CalibrationBin } from "@/lib/data/types";

// Plot geometry in viewBox units: a square plot with room for ticks and axis titles.
const SIZE = 300;
const PAD = { left: 56, right: 20, top: 12, bottom: 40 };
const PLOT = SIZE - PAD.left - PAD.right;
const TICKS = [0, 0.25, 0.5, 0.75, 1];

const x = (p: number) => PAD.left + p * PLOT;
const y = (p: number) => PAD.top + (1 - p) * PLOT;

type Point = CalibrationBin & { meanPred: number; observed: number };

/** Predicted vs observed win rate per bin, with the perfect-calibration diagonal. */
export function CalibrationChart({
  title,
  model,
  bins,
}: {
  title: string;
  model: string;
  bins: CalibrationBin[] | null;
}) {
  if (!bins) {
    return (
      <figure>
        <figcaption className="mb-3 font-medium text-silver">
          {title}
        </figcaption>
        <EmptyState title="Not available">
          Away-win calibration isn&apos;t stored for this model&apos;s backtest.
        </EmptyState>
      </figure>
    );
  }

  const points = bins.filter(
    (b): b is Point => b.n > 0 && b.meanPred !== null && b.observed !== null,
  );
  const total = points.reduce((s, b) => s + b.n, 0);
  const maxN = Math.max(1, ...points.map((b) => b.n));
  // Area proportional to n; 4px radius (8px marker) at the smallest.
  const radius = (n: number) => 4 + 8 * Math.sqrt(n / maxN);
  const gap = total
    ? points.reduce((s, b) => s + b.n * Math.abs(b.observed - b.meanPred), 0) /
      total
    : 0;
  const label = `${title} calibration of the ${model} model on ${total} test matches in ${points.length} groups. On average the observed rate is ${(gap * 100).toFixed(1)} percentage points from the predicted chance.`;

  return (
    <figure>
      <figcaption className="mb-3 font-medium text-silver">{title}</figcaption>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="w-full max-w-[22rem] text-mist"
        role="img"
        aria-label={label}
      >
        {TICKS.map((t) => (
          <g key={t}>
            <line
              x1={x(0)}
              x2={x(1)}
              y1={y(t)}
              y2={y(t)}
              className="stroke-rowline"
              strokeWidth={1}
            />
            <line
              x1={x(t)}
              x2={x(t)}
              y1={y(0)}
              y2={y(1)}
              className="stroke-rowline"
              strokeWidth={1}
            />
            <text
              x={x(t)}
              y={y(0) + 16}
              textAnchor="middle"
              fontSize={11}
              fill="currentColor"
            >
              {formatPct(t)}
            </text>
            <text
              x={x(0) - 6}
              y={y(t) + 4}
              textAnchor="end"
              fontSize={11}
              fill="currentColor"
            >
              {formatPct(t)}
            </text>
          </g>
        ))}
        <line
          x1={x(0)}
          y1={y(0)}
          x2={x(1)}
          y2={y(1)}
          className="stroke-muted"
          strokeWidth={1.5}
          strokeDasharray="4 4"
        />
        <text
          x={x(0.5)}
          y={SIZE - 4}
          textAnchor="middle"
          fontSize={11}
          fill="currentColor"
        >
          Predicted chance
        </text>
        <text
          transform={`translate(12 ${y(0.5)}) rotate(-90)`}
          textAnchor="middle"
          fontSize={11}
          fill="currentColor"
        >
          Actually happened
        </text>
        {points.map((b) => (
          <g key={b.lo}>
            <title>
              {`Predicted ${formatPct(b.meanPred)}, happened ${formatPct(b.observed)} (${b.n} matches)`}
            </title>
            {/* Larger transparent hit target for the hover tooltip. */}
            <circle
              cx={x(b.meanPred)}
              cy={y(b.observed)}
              r={Math.max(radius(b.n), 12)}
              fill="transparent"
            />
            <circle
              cx={x(b.meanPred)}
              cy={y(b.observed)}
              r={radius(b.n)}
              className="fill-floodlight stroke-night"
              fillOpacity={0.85}
              strokeWidth={2}
            />
          </g>
        ))}
      </svg>

      <details className="mt-1 text-sm">
        <summary className="cursor-pointer py-2 text-floodlight">
          {title} calibration as a table
        </summary>
        <table className="mt-2 w-full max-w-[22rem]">
          <thead className="text-xs text-mist">
            <tr className="border-b border-line">
              <th scope="col" className="py-1.5 text-left font-normal">
                Predicted range
              </th>
              <th scope="col" className="py-1.5 text-right font-normal">
                Mean predicted
              </th>
              <th scope="col" className="py-1.5 text-right font-normal">
                Happened
              </th>
              <th scope="col" className="py-1.5 text-right font-normal">
                Matches
              </th>
            </tr>
          </thead>
          <tbody>
            {bins.map((b) => (
              <tr key={b.lo} className="border-b border-rowline">
                <th scope="row" className="py-1.5 text-left font-normal">
                  {formatPct(b.lo)}–{formatPct(b.hi)}
                </th>
                <td className="py-1.5 text-right">
                  {b.meanPred === null ? "–" : formatPct(b.meanPred, 1)}
                </td>
                <td className="py-1.5 text-right">
                  {b.observed === null ? "–" : formatPct(b.observed, 1)}
                </td>
                <td className="py-1.5 text-right">{b.n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
