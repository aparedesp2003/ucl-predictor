import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingBlock, Skeleton } from "@/components/skeleton";

import { BacktestSection, Headline, LiveTable, Predictions } from "./sections";

export const metadata: Metadata = {
  title: "Accuracy",
  description:
    "How the predictions score against real results this season, every prediction with its outcome, and how the models did on five past seasons.",
};

const sectionTitle = "font-display text-2xl font-semibold";

function RowsSkeleton({ rows, label }: { rows: number; label: string }) {
  return (
    <LoadingBlock label={label}>
      <div className="space-y-2">
        {Array.from({ length: rows }, (_, i) => (
          <Skeleton key={i} className="h-9" />
        ))}
      </div>
    </LoadingBlock>
  );
}

export default function AccuracyPage() {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <p className="text-sm font-medium tracking-wide text-floodlight uppercase">
        Accuracy
      </p>
      <Suspense
        fallback={
          <LoadingBlock label="Loading this season's score">
            <Skeleton className="mt-2 h-12 w-full max-w-xl" />
            <Skeleton className="mt-3 h-5 w-full max-w-md" />
          </LoadingBlock>
        }
      >
        <Headline />
      </Suspense>

      <div className="mt-6 max-w-[70ch] space-y-2 text-sm text-mist">
        <p>
          <span className="font-medium text-silver">Log loss</span> measures how
          surprised the model was by what actually happened; lower is better,
          and guessing a third for each outcome scores 1.099.
        </p>
        <p>
          <span className="font-medium text-silver">RPS</span> (ranked
          probability score) measures how far the home, draw and away split was
          from the result, counting a near miss as less wrong than a far one;
          lower is better.
        </p>
      </div>

      <section aria-labelledby="live" className="mt-12">
        <h2 id="live" className={sectionTitle}>
          This season
        </h2>
        <p className="mt-1 mb-5 text-sm text-mist">
          Only predictions saved before kick-off count, scored on the 90-minute
          result.
        </p>
        <Suspense
          fallback={<RowsSkeleton rows={4} label="Loading live scores" />}
        >
          <LiveTable />
        </Suspense>
      </section>

      <section aria-labelledby="every" className="mt-14">
        <h2 id="every" className={sectionTitle}>
          Every prediction
        </h2>
        <p className="mt-1 mb-5 text-sm text-mist">
          The primary model&apos;s call for each finished match, newest first. A
          hit means the outcome it rated most likely happened.
        </p>
        <Suspense
          fallback={<RowsSkeleton rows={8} label="Loading predictions" />}
        >
          <Predictions />
        </Suspense>
      </section>

      <section aria-labelledby="backtest" className="mt-14">
        <h2 id="backtest" className={sectionTitle}>
          Backtest, 2021-22 to 2025-26
        </h2>
        <p className="mt-1 mb-5 max-w-[70ch] text-sm text-mist">
          Before the season, each candidate model predicted five past seasons it
          had not been tuned on. The primary model was chosen on earlier
          validation seasons, before these numbers were looked at.
        </p>
        <Suspense
          fallback={<RowsSkeleton rows={7} label="Loading backtest results" />}
        >
          <BacktestSection />
        </Suspense>
      </section>
    </main>
  );
}
