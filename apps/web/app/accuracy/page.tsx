import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingBlock, Skeleton } from "@/components/skeleton";
import { pageMetadata } from "@/lib/site";

import {
  BacktestSection,
  Hero,
  LandedAndUpsets,
  MatchdayTiles,
  ModelLanes,
  Predictions,
} from "./sections";

export const metadata: Metadata = pageMetadata({
  title: "Accuracy",
  description:
    "How the predictions score against real results this season, every prediction with its outcome, and how the models did on five past seasons.",
  path: "/accuracy",
});

const h2 = "font-display text-3xl font-semibold";

function Blocks({
  label,
  count,
  className,
}: {
  label: string;
  count: number;
  className: string;
}) {
  return (
    <LoadingBlock label={label}>
      <div className="space-y-3">
        {Array.from({ length: count }, (_, i) => (
          <Skeleton key={i} className={className} />
        ))}
      </div>
    </LoadingBlock>
  );
}

export default function AccuracyPage() {
  return (
    <main id="main" className="mx-auto max-w-6xl space-y-20 px-4 py-12 sm:px-6">
      <Suspense
        fallback={
          <LoadingBlock label="Loading this season's scorecard">
            <Skeleton className="h-5 w-56" />
            <Skeleton className="mt-4 h-32 w-full max-w-xl" />
            <Skeleton className="mt-4 h-6 w-full max-w-lg" />
          </LoadingBlock>
        }
      >
        <Hero />
      </Suspense>

      <section aria-labelledby="surprise">
        <h2 id="surprise" className={h2}>
          How surprised was each model?
        </h2>
        <p className="mt-2 mb-6 max-w-[65ch] text-mist">
          Log loss measures how surprised a model was by what actually happened:
          a shorter bar means a sharper model, and guessing a third each scores
          1.099.
        </p>
        <Suspense
          fallback={
            <Blocks label="Loading live scores" count={3} className="h-10" />
          }
        >
          <ModelLanes />
        </Suspense>
      </section>

      <section aria-labelledby="matchdays">
        <h2 id="matchdays" className={h2}>
          Matchday by matchday
        </h2>
        <p className="mt-2 mb-6 max-w-[65ch] text-mist">
          How many favourites came through in each league-phase matchday.
        </p>
        <Suspense
          fallback={
            <LoadingBlock label="Loading matchdays">
              <div className="grid grid-cols-[repeat(auto-fit,minmax(7.5rem,1fr))] gap-3">
                {Array.from({ length: 8 }, (_, i) => (
                  <Skeleton key={i} className="h-32 rounded-xl" />
                ))}
              </div>
            </LoadingBlock>
          }
        >
          <MatchdayTiles />
        </Suspense>
      </section>

      <Suspense fallback={null}>
        <LandedAndUpsets />
      </Suspense>

      <section aria-labelledby="every">
        <h2 id="every" className={h2}>
          Every prediction
        </h2>
        <p className="mt-2 mb-6 max-w-[65ch] text-mist">
          The main model&apos;s call for each finished match, newest first. A
          hit means the outcome it rated most likely happened, on the 90-minute
          result.
        </p>
        <Suspense
          fallback={
            <Blocks
              label="Loading predictions"
              count={4}
              className="h-36 rounded-xl"
            />
          }
        >
          <Predictions />
        </Suspense>
      </section>

      <Suspense
        fallback={
          <Blocks label="Loading backtest results" count={7} className="h-7" />
        }
      >
        <BacktestSection />
      </Suspense>
    </main>
  );
}
