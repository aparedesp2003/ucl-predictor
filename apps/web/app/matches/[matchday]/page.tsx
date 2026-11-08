import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { Suspense } from "react";

import { EmptyState } from "@/components/empty-state";
import { LoadingBlock, Skeleton } from "@/components/skeleton";
import { leagueMatches } from "@/lib/data/derive";
import { getSeasonMatches } from "@/lib/data/matches";
import { safely } from "@/lib/data/safe";
import { LEAGUE_MATCHDAYS } from "@/lib/site";
import { cn } from "@/lib/utils";

import { MatchdayTable } from "./matchday-table";

const MATCHDAYS = Array.from({ length: LEAGUE_MATCHDAYS }, (_, i) => i + 1);

export function generateStaticParams() {
  return MATCHDAYS.map((md) => ({ matchday: String(md) }));
}

function parseMatchday(value: string): number | null {
  const md = Number(value);
  return Number.isInteger(md) &&
    md >= 1 &&
    md <= LEAGUE_MATCHDAYS &&
    String(md) === value
    ? md
    : null;
}

export async function generateMetadata({
  params,
}: PageProps<"/matches/[matchday]">): Promise<Metadata> {
  const md = parseMatchday((await params).matchday);
  return { title: md ? `Matchday ${md} predictions` : "Matches" };
}

function TableSkeleton() {
  return (
    <LoadingBlock label="Loading matches">
      <div className="space-y-2">
        {Array.from({ length: 9 }, (_, i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    </LoadingBlock>
  );
}

// The shell renders instantly; everything that depends on the URL streams in below it.
export default function MatchdayPage({
  params,
}: PageProps<"/matches/[matchday]">) {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <p className="text-sm font-medium tracking-wide text-floodlight uppercase">
        League phase
      </p>
      <Suspense
        fallback={
          <>
            <Skeleton className="mt-3 h-10 w-56" />
            <Skeleton className="mt-6 mb-8 h-11 w-full max-w-md" />
            <TableSkeleton />
          </>
        }
      >
        <Matchday params={params} />
      </Suspense>
    </main>
  );
}

async function Matchday({
  params,
}: Pick<PageProps<"/matches/[matchday]">, "params">) {
  const md = parseMatchday((await params).matchday);
  if (!md) notFound();

  return (
    <>
      <h1 className="mt-2 font-display text-4xl font-semibold">
        Matchday {md}
      </h1>

      <nav aria-label="Matchdays" className="mt-6">
        <ul className="flex flex-wrap gap-2">
          {MATCHDAYS.map((n) => (
            <li key={n}>
              <Link
                href={`/matches/${n}`}
                aria-current={n === md ? "page" : undefined}
                aria-label={`Matchday ${n}`}
                className={cn(
                  "flex size-11 items-center justify-center rounded-sm border text-sm",
                  n === md
                    ? "border-floodlight bg-floodlight font-semibold text-night"
                    : "border-line text-mist hover:border-mist hover:text-starlight",
                )}
              >
                {n}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <section aria-label={`Matchday ${md} matches`} className="mt-8">
        <Suspense fallback={<TableSkeleton />}>
          <MatchdayMatches matchday={md} />
        </Suspense>
      </section>
    </>
  );
}

async function MatchdayMatches({ matchday }: { matchday: number }) {
  await connection();
  const matches = await safely(getSeasonMatches);
  if (matches === null) {
    return (
      <EmptyState title="Matches are unavailable right now">
        Please try again later.
      </EmptyState>
    );
  }
  const rows = leagueMatches(matches, matchday).sort(
    (a, b) => a.kickoff.localeCompare(b.kickoff) || a.id - b.id,
  );
  if (!rows.length) {
    return (
      <EmptyState title={`No matchday ${matchday} fixtures yet`}>
        Fixtures appear here once they are published.
      </EmptyState>
    );
  }
  return <MatchdayTable rows={rows} />;
}
