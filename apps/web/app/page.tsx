import { Suspense } from "react";

import { LoadingBlock, Skeleton } from "@/components/skeleton";

import {
  BoldestCalls,
  Hero,
  RaceSection,
  ReportCard,
  TickerSection,
} from "./_home/sections";

function HeroSkeleton() {
  return (
    <LoadingBlock label="Loading the closest call">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <Skeleton className="mx-auto h-8 w-64 rounded-full" />
        <Skeleton className="mx-auto mt-6 h-16 w-full max-w-3xl" />
        <Skeleton className="mx-auto mt-8 h-56 w-full max-w-[760px] rounded-[20px]" />
      </div>
    </LoadingBlock>
  );
}

function CardsSkeleton() {
  return (
    <LoadingBlock label="Loading the boldest calls">
      <div className="flex gap-4 overflow-hidden">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-36 w-[300px] shrink-0 rounded-xl" />
        ))}
      </div>
    </LoadingBlock>
  );
}

function RaceSkeleton() {
  return (
    <LoadingBlock label="Loading the race for the trophy">
      <Skeleton className="mb-5 h-12 w-80 max-w-full rounded-xl" />
      <div className="space-y-2">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-[34px] rounded-[10px]" />
        ))}
      </div>
    </LoadingBlock>
  );
}

const sectionTitle = "font-display text-2xl font-semibold";

export default function HomePage() {
  return (
    <main id="main">
      <Suspense fallback={<div className="h-[50px] border-b border-line" />}>
        <TickerSection />
      </Suspense>

      <Suspense fallback={<HeroSkeleton />}>
        <Hero />
      </Suspense>

      <div className="mx-auto max-w-6xl space-y-16 px-4 py-14 sm:px-6">
        <section aria-labelledby="boldest-calls">
          <h2 id="boldest-calls" className={sectionTitle}>
            The model&apos;s boldest calls
          </h2>
          <p className="mt-1 mb-5 text-sm text-mist">
            The next matchday&apos;s fixtures where the model backs one side
            most strongly.
          </p>
          <Suspense fallback={<CardsSkeleton />}>
            <BoldestCalls />
          </Suspense>
        </section>

        <section aria-labelledby="race">
          <h2 id="race" className={sectionTitle}>
            The race for the trophy
          </h2>
          <p className="mt-1 mb-5 text-sm text-mist">
            The eight likeliest clubs for each round, from the season simulator.
          </p>
          <Suspense fallback={<RaceSkeleton />}>
            <RaceSection />
          </Suspense>
        </section>

        <Suspense fallback={null}>
          <ReportCard />
        </Suspense>
      </div>
    </main>
  );
}
