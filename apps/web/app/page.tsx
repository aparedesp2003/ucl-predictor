import { Suspense } from "react";

import { LoadingBlock, Skeleton } from "@/components/skeleton";

import { BiggestCalls, Hero, KeepingScore, TitleRace } from "./_home/sections";

function HeroSkeleton() {
  return (
    <LoadingBlock label="Loading this matchday">
      <Skeleton className="h-4 w-48" />
      <Skeleton className="mt-3 h-12 w-full max-w-2xl" />
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
      </div>
    </LoadingBlock>
  );
}

function CardsSkeleton() {
  return (
    <LoadingBlock label="Loading predictions">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-44" />
        ))}
      </div>
    </LoadingBlock>
  );
}

function RowsSkeleton({ rows, label }: { rows: number; label: string }) {
  return (
    <LoadingBlock label={label}>
      <div className="space-y-2">
        {Array.from({ length: rows }, (_, i) => (
          <Skeleton key={i} className="h-8" />
        ))}
      </div>
    </LoadingBlock>
  );
}

const sectionTitle = "font-display text-2xl font-semibold";

export default function HomePage() {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <Suspense fallback={<HeroSkeleton />}>
        <Hero />
      </Suspense>

      <div className="mt-14 grid gap-14 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 space-y-14">
          <section aria-labelledby="calls">
            <h2 id="calls" className={sectionTitle}>
              Biggest calls this matchday
            </h2>
            <p className="mt-1 mb-5 text-sm text-mist">
              The matches where the model backs one side most strongly.
            </p>
            <Suspense fallback={<CardsSkeleton />}>
              <BiggestCalls />
            </Suspense>
          </section>

          <section aria-labelledby="title-race">
            <h2 id="title-race" className={sectionTitle}>
              Title race
            </h2>
            <p className="mt-1 mb-5 text-sm text-mist">
              The eight likeliest winners, with their chance of reaching the
              last 16.
            </p>
            <Suspense
              fallback={<RowsSkeleton rows={8} label="Loading title odds" />}
            >
              <TitleRace />
            </Suspense>
          </section>
        </div>

        <aside className="space-y-10" aria-label="About the predictions">
          <section aria-labelledby="keeping-score">
            <h2
              id="keeping-score"
              className="font-display text-xl font-semibold"
            >
              Keeping score
            </h2>
            <div className="mt-3">
              <Suspense
                fallback={<RowsSkeleton rows={3} label="Loading scores" />}
              >
                <KeepingScore />
              </Suspense>
            </div>
          </section>

          <section aria-labelledby="how-it-works">
            <h2
              id="how-it-works"
              className="font-display text-xl font-semibold"
            >
              How it works
            </h2>
            <div className="mt-3 space-y-3 text-sm text-mist">
              <p>
                Ratings built from every Champions League match since 2011-12
                turn each fixture into home, draw and away probabilities.
              </p>
              <p>
                Every prediction is saved before kick-off and never edited
                afterwards. Only those saved predictions are scored once the
                result is in.
              </p>
              <p>
                The remaining fixtures are then played out thousands of times to
                estimate each club&apos;s chance of the last 16 and the title.
              </p>
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}
