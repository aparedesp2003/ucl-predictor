import type { Metadata } from "next";

import { pageMetadata } from "@/lib/site";
import { connection } from "next/server";
import { Suspense } from "react";

import { EmptyState } from "@/components/empty-state";
import { LoadingBlock, Skeleton } from "@/components/skeleton";
import { getTitleRace } from "@/lib/data/odds";
import { safely } from "@/lib/data/safe";

import { SimulatorTable } from "./simulator-table";

export const metadata: Metadata = pageMetadata({
  title: "Season simulator",
  description:
    "Every club's chance of the top 8, the play-offs, each knockout round and the title, from thousands of simulated Champions League seasons.",
  path: "/simulator",
});

export default function SimulatorPage() {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <p className="text-sm font-medium tracking-wide text-floodlight uppercase">
        Simulator
      </p>
      <h1 className="mt-2 font-display text-4xl font-semibold">
        How the season could finish
      </h1>
      <p className="mt-3 max-w-[70ch] text-mist">
        The rest of the season played out many times from the current ratings.
        Each column is the share of simulated seasons in which the club got that
        far. Select a column heading to sort by it.
      </p>
      <div className="mt-8">
        <Suspense fallback={<TableSkeleton />}>
          <Simulation />
        </Suspense>
      </div>
    </main>
  );
}

function TableSkeleton() {
  return (
    <LoadingBlock label="Loading the simulation">
      <div className="space-y-2">
        {Array.from({ length: 12 }, (_, i) => (
          <Skeleton key={i} className="h-10" />
        ))}
      </div>
    </LoadingBlock>
  );
}

async function Simulation() {
  await connection();
  const race = await safely(getTitleRace);
  if (!race?.teams.length) {
    return (
      <EmptyState title="No simulation yet">
        The season is simulated after each matchday; the table appears after the
        first run.
      </EmptyState>
    );
  }
  return <SimulatorTable race={race} />;
}
