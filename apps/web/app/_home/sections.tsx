import Link from "next/link";
import { connection } from "next/server";

import { EmptyState } from "@/components/empty-state";
import { LocalDateRange } from "@/components/local-time";
import { MatchCallCard } from "@/components/match-call-card";
import { TeamBadge } from "@/components/team-badge";
import {
  biggestCalls,
  currentMatchday,
  formatPct,
  improvementOverGuessing,
  isLocked,
  kickoffRange,
  leagueMatches,
  teamName,
  titleHeadline,
} from "@/lib/data/derive";
import { getSeasonMatches } from "@/lib/data/matches";
import { getTitleRace } from "@/lib/data/odds";
import { safely } from "@/lib/data/safe";
import { modelLabel } from "@/lib/models/labels";
import { getScoreboard } from "@/lib/data/scoreboard";
import type { MatchRow, Prediction, ScoreRow } from "@/lib/data/types";
import { teamColors } from "@/lib/teams/colors";
import { formatDate } from "@/lib/time";

const FALLBACK_HEADLINE = "Champions League predictions, match by match";

// Every section reads at request time: connection() keeps database reads out of the build.
async function loadSeason() {
  await connection();
  const matches = (await safely(getSeasonMatches)) ?? [];
  const season = matches[0]?.season ?? null;
  const scores = season
    ? ((await safely(() => getScoreboard(season))) ?? [])
    : [];
  return { matches, season, scores };
}

export async function Hero() {
  await connection(); // before any read starts, including the parallel ones below
  const [{ matches, scores }, race] = await Promise.all([
    loadSeason(),
    safely(getTitleRace),
  ]);
  const matchday = currentMatchday(matches);
  const range = kickoffRange(leagueMatches(matches, matchday));
  const leader = race?.teams[0];
  const primary = scores.find((s) => s.isPrimary);

  return (
    <div>
      {range ? (
        <p className="text-sm font-medium tracking-wide text-floodlight uppercase">
          Matchday {matchday} ·{" "}
          <LocalDateRange first={range.first} last={range.last} />
        </p>
      ) : null}
      <h1 className="mt-2 max-w-3xl font-display text-4xl leading-tight font-semibold sm:text-5xl">
        {(race && titleHeadline(race.teams)) ?? FALLBACK_HEADLINE}
      </h1>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <section
          aria-labelledby="stat-favourite"
          className="rounded-md border border-line bg-midnight p-5"
        >
          <h2 id="stat-favourite" className="text-sm text-mist">
            Title favourite
          </h2>
          {leader ? (
            <>
              <p className="mt-3 flex items-center gap-3 text-lg font-medium">
                <TeamBadge team={leader.team} size="md" />
                {teamName(leader.team)}
              </p>
              <p className="mt-2 text-3xl font-semibold">
                {formatPct(leader.pWin, 1)}
              </p>
              <p className="text-sm text-mist">chance to win the competition</p>
            </>
          ) : (
            <p className="mt-3 text-mist">
              No simulation has been run for this season yet.
            </p>
          )}
        </section>
        <section
          aria-labelledby="stat-record"
          className="rounded-md border border-line bg-midnight p-5"
        >
          <h2 id="stat-record" className="text-sm text-mist">
            Track record
          </h2>
          {primary ? (
            <TrackRecord row={primary} />
          ) : (
            <p className="mt-3 text-mist">
              Scoring starts after the first matchday.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function TrackRecord({ row }: { row: ScoreRow }) {
  const gain = improvementOverGuessing(row);
  return (
    <>
      <p className="mt-3 text-3xl font-semibold">
        {formatPct(Math.abs(gain), 1)}
      </p>
      <p className="text-sm text-mist">
        {gain >= 0 ? "lower" : "higher"} log loss than guessing, over {row.n}{" "}
        match
        {row.n === 1 ? "" : "es"} scored ({modelLabel(row.model, "live")} model)
      </p>
    </>
  );
}

export async function BiggestCalls() {
  const { matches } = await loadSeason();
  const matchday = currentMatchday(matches);
  const calls = biggestCalls(leagueMatches(matches, matchday)) as (MatchRow & {
    prediction: Prediction;
  })[];

  return (
    <>
      {calls.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {calls.map((m) => (
            <MatchCallCard key={m.id} match={m} locked={isLocked(m)} />
          ))}
        </div>
      ) : (
        <EmptyState title="No predictions for this matchday yet">
          Predictions appear once the fixtures are confirmed.
        </EmptyState>
      )}
      {matches.length ? (
        <p className="mt-4">
          <Link
            href={`/matches/${matchday}`}
            className="text-floodlight hover:underline"
          >
            All matchday {matchday} matches
          </Link>
        </p>
      ) : null}
    </>
  );
}

export async function TitleRace() {
  await connection();
  const race = await safely(getTitleRace);
  if (!race?.teams.length) {
    return (
      <EmptyState title="No title odds yet">
        The season has not been simulated yet.
      </EmptyState>
    );
  }
  const top = race.teams.slice(0, 8);
  const leaderWin = top[0].pWin || 1;

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[22rem] text-sm">
          <thead className="text-left text-xs text-mist">
            <tr className="border-b border-line">
              <th scope="col" className="w-8 py-2 font-normal">
                <span className="sr-only">Rank</span>
              </th>
              <th scope="col" className="py-2 font-normal">
                Team
              </th>
              <th
                scope="col"
                className="hidden w-1/3 py-2 font-normal sm:table-cell"
              >
                <span className="sr-only">
                  Win chance relative to the favourite
                </span>
              </th>
              <th scope="col" className="py-2 pl-3 text-right font-normal">
                Last 16
              </th>
              <th scope="col" className="py-2 pl-3 text-right font-normal">
                Win
              </th>
            </tr>
          </thead>
          <tbody>
            {top.map((t, i) => (
              <tr key={t.team.id} className="border-b border-rowline">
                <td className="py-2.5 text-mist">{i + 1}</td>
                <th scope="row" className="py-2.5 text-left font-medium">
                  <span className="flex items-center gap-2">
                    <TeamBadge team={t.team} size="sm" />
                    {teamName(t.team)}
                  </span>
                </th>
                <td className="hidden py-2.5 sm:table-cell" aria-hidden>
                  <div className="h-2 rounded-[1px] bg-rowline">
                    <div
                      className="h-full rounded-[1px] ring-1 ring-white/18 ring-inset"
                      style={{
                        width: `${(t.pWin / leaderWin) * 100}%`,
                        backgroundColor: teamColors(t.team).primary,
                      }}
                    />
                  </div>
                </td>
                <td className="py-2.5 pl-3 text-right text-mist">
                  {formatPct(t.pR16)}
                </td>
                <td className="py-2.5 pl-3 text-right font-semibold">
                  {formatPct(t.pWin, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-sm text-mist">
        {race.nSims.toLocaleString("en-GB")} simulated seasons · results through{" "}
        {formatDate(race.resultsThrough)}
      </p>
    </>
  );
}

export async function KeepingScore() {
  const { scores } = await loadSeason();
  const sorted = [...scores].sort((a, b) => a.logLoss - b.logLoss);
  const n = Math.max(0, ...scores.map((s) => s.n));
  const guessing = scores[0]?.uniformLogLoss ?? Math.log(3);

  return (
    <>
      <table className="w-full text-sm">
        <caption className="sr-only">
          Average log loss per model this season, lower is better
        </caption>
        <thead className="text-left text-xs text-mist">
          <tr className="border-b border-line">
            <th scope="col" className="py-2 font-normal">
              Model
            </th>
            <th scope="col" className="py-2 text-right font-normal">
              Log loss
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => (
            <tr key={s.model} className="border-b border-rowline">
              <th scope="row" className="py-2 text-left font-medium">
                {modelLabel(s.model, "live")}
                {s.isPrimary ? (
                  <span className="ml-2 text-xs font-normal text-mist">
                    primary
                  </span>
                ) : null}
              </th>
              <td className="py-2 text-right">{s.logLoss.toFixed(3)}</td>
            </tr>
          ))}
          <tr className="border-b border-rowline">
            <th scope="row" className="py-2 text-left font-medium text-mist">
              Guessing
            </th>
            <td className="py-2 text-right text-mist">{guessing.toFixed(3)}</td>
          </tr>
        </tbody>
      </table>
      <p className="mt-3 text-sm text-mist">
        {n > 0
          ? `Lower is better. ${n} match${n === 1 ? "" : "es"} scored this season, each predicted before kick-off.`
          : "Scoring starts after the first matchday. Guessing means a third for each outcome."}
      </p>
    </>
  );
}
