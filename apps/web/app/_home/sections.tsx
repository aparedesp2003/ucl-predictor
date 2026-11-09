import Link from "next/link";
import { connection } from "next/server";

import { Countdown } from "@/components/countdown";
import { EmptyState } from "@/components/empty-state";
import { GrowOnMount } from "@/components/grow-on-mount";
import { LocalTime } from "@/components/local-time";
import { getCurrentSeason, getScoredPredictions } from "@/lib/data/accuracy";
import { formatPct, teamName, titleHeadline } from "@/lib/data/derive";
import {
  boldestCalls,
  closestCall,
  favouriteSide,
  heroBarColors,
  lastCompletedMatchday,
  matchdayFixtures,
  nextMatchday,
  pct,
  type PredictedMatch,
  reportCard,
  tickerOutcomes,
} from "@/lib/data/home";
import { getSeasonMatches } from "@/lib/data/matches";
import { getTitleRace } from "@/lib/data/odds";
import { safely } from "@/lib/data/safe";
import type { TitleOdds } from "@/lib/data/types";
import { badgeColors, clashColors } from "@/lib/teams/colors";
import { displayCode } from "@/lib/teams/display";
import { formatDate } from "@/lib/time";
import { cn } from "@/lib/utils";

import { Race } from "./race";
import { Ticker, type TickerItem } from "./ticker";

const MISS = "#F5A35C";
const sectionTitle = "font-display text-2xl font-semibold";
const inlineLink =
  "text-floodlight underline decoration-floodlight/40 underline-offset-2 hover:decoration-floodlight";

// Every section reads at request time: connection() keeps database reads out of the build.
async function loadUpcoming() {
  await connection();
  const matches = (await safely(getSeasonMatches)) ?? [];
  const md = nextMatchday(matches);
  return {
    matches,
    md,
    fixtures: md === null ? [] : matchdayFixtures(matches, md),
  };
}

// --- a) Ticker ----------------------------------------------------------------------------------

export async function TickerSection() {
  const { fixtures } = await loadUpcoming();
  const items: TickerItem[] = fixtures
    .filter((m): m is PredictedMatch => m.prediction !== null)
    .map((m) => ({
      id: m.id,
      kickoff: m.kickoff,
      homeCode: displayCode(m.home),
      awayCode: displayCode(m.away),
      homeName: teamName(m.home),
      awayName: teamName(m.away),
      outcomes: tickerOutcomes(m.prediction).map((o) => ({
        pct: pct(o.p),
        favoured: o.favoured,
      })),
    }));
  return items.length ? <Ticker items={items} /> : null;
}

// --- b) Hero ------------------------------------------------------------------------------------

export async function Hero() {
  await connection();
  const [{ fixtures, md }, race] = await Promise.all([
    loadUpcoming(),
    safely(getTitleRace),
  ]);
  const call = closestCall(fixtures);
  if (call && md !== null) return <ClosestCall match={call} matchday={md} />;
  const leader = race?.teams[0];
  if (leader) return <Favourite leader={leader} teams={race.teams} />;
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-4xl font-semibold">
        Champions League predictions, match by match
      </h1>
      <div className="mt-6">
        <EmptyState title="Nothing to show yet">
          Predictions appear once the fixtures are confirmed.
        </EmptyState>
      </div>
    </div>
  );
}

const SPLIT_LEFT = "polygon(0 0, 58% 0, 42% 100%, 0 100%)";
const SPLIT_RIGHT = "polygon(58% 0, 100% 0, 100% 100%, 42% 100%)";

/**
 * Name size: 48px on phones and 84px from md, smaller when the longest word would not fit its half
 * (Barlow Condensed Bold capitals average under 0.45em). Names wrap only between words.
 */
function nameFontSize(...names: string[]): string {
  const longest = Math.max(
    ...names.flatMap((n) => n.split(/\s+/).map((w) => w.length)),
  );
  return `min(var(--name-cap), calc((min(100vw, 72rem) - 8rem) / ${(longest * 0.9).toFixed(1)}))`;
}

function ClosestCall({
  match: m,
  matchday,
}: {
  match: PredictedMatch;
  matchday: number;
}) {
  const colors = clashColors(m.home, m.away);
  const bars = heroBarColors(m.home, m.away);
  const homeText = badgeColors(m.home, colors.home).text;
  const awayText = badgeColors(m.away, colors.away).text;
  const home = teamName(m.home);
  const away = teamName(m.away);
  const p = m.prediction;
  const numbers = [
    {
      label: `${home} win`,
      value: p.pHome,
      size: "text-[56px] sm:text-[72px]",
    },
    { label: "Draw", value: p.pDraw, size: "text-[40px] sm:text-[52px]" },
    {
      label: `${away} win`,
      value: p.pAway,
      size: "text-[56px] sm:text-[72px]",
    },
  ];
  const segments = [
    { value: p.pHome, color: bars[0] },
    { value: p.pDraw, color: bars[1] },
    { value: p.pAway, color: bars[2] },
  ];

  return (
    <section
      aria-labelledby="hero-title"
      className="relative isolate overflow-hidden border-b border-line"
    >
      <div aria-hidden className="absolute inset-0 -z-10">
        <div
          className="absolute inset-0"
          style={{ backgroundColor: colors.home, clipPath: SPLIT_LEFT }}
        />
        <div
          className="absolute inset-0"
          style={{ backgroundColor: colors.away, clipPath: SPLIT_RIGHT }}
        />
        <div className="absolute top-[38%] left-1/2 size-56 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white/18 md:size-80" />
      </div>

      <div className="mx-auto max-w-6xl px-4 pt-10 pb-12 sm:px-6 md:pt-14 md:pb-16">
        <p className="mx-auto w-fit rounded-full bg-night px-4 py-1.5 text-sm font-medium tracking-wide text-floodlight uppercase">
          Closest call of matchday {matchday}
        </p>
        <h1
          id="hero-title"
          aria-label={`${home} vs ${away}`}
          className={cn(
            "mt-6 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 font-score leading-[0.95] font-bold uppercase [--name-cap:48px] md:gap-6 md:[--name-cap:84px]",
          )}
          style={{ fontSize: nameFontSize(home, away) }}
        >
          <span
            className="[overflow-wrap:anywhere]"
            style={{ color: homeText }}
          >
            {home}
          </span>
          <span className="rounded-full bg-night px-3 py-1 text-base text-starlight normal-case md:text-xl">
            vs
          </span>
          <span
            className="text-right [overflow-wrap:anywhere]"
            style={{ color: awayText }}
          >
            {away}
          </span>
        </h1>

        <div className="mx-auto mt-8 max-w-[760px] rounded-[20px] bg-night p-5 sm:p-7">
          <dl className="grid grid-cols-3 items-start gap-2 text-center">
            {numbers.map((n) => (
              <div key={n.label} className="flex flex-col-reverse">
                <dt className="mt-1 text-sm text-balance text-mist">
                  {n.label}
                </dt>
                <dd
                  className={cn(
                    "flex h-[56px] items-end justify-center font-score leading-none font-bold sm:h-[72px]",
                    n.size,
                  )}
                >
                  {formatPct(n.value)}
                </dd>
              </div>
            ))}
          </dl>
          <GrowOnMount className="mt-5">
            <div aria-hidden className="flex h-3.5 gap-[3px]">
              {segments.map((s, i) => (
                <span
                  key={i}
                  className="grow-bar block h-full rounded-[3px] ring-1 ring-white/18 ring-inset"
                  style={{
                    width: `calc(${s.value * 100}% - 2px)`,
                    backgroundColor: s.color,
                  }}
                />
              ))}
            </div>
          </GrowOnMount>
          <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-mist">
              Kick-off{" "}
              <LocalTime
                iso={m.kickoff}
                format="dayTime"
                className="font-medium text-starlight"
              />{" "}
              your time
            </p>
            <Countdown kickoff={m.kickoff} />
          </div>
        </div>
      </div>
    </section>
  );
}

function Favourite({
  leader,
  teams,
}: {
  leader: TitleOdds;
  teams: TitleOdds[];
}) {
  const { background, text } = badgeColors(leader.team);
  return (
    <section aria-labelledby="hero-title" className="border-b border-line">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 md:py-16">
        <p className="text-sm font-medium tracking-wide text-floodlight uppercase">
          Title favourite
        </p>
        <h1
          id="hero-title"
          className="mt-2 font-display text-4xl leading-tight font-semibold sm:text-5xl"
        >
          {titleHeadline(teams)}
        </h1>
        <div
          className="mt-8 max-w-[760px] rounded-[20px] p-6 sm:p-8"
          style={{ backgroundColor: background, color: text }}
        >
          <p className="font-score text-5xl font-bold uppercase sm:text-7xl">
            {teamName(leader.team)}
          </p>
          <p className="mt-2 text-lg">
            <span className="font-score text-4xl font-bold">
              {formatPct(leader.pWin, 1)}
            </span>{" "}
            to win the competition
          </p>
        </div>
      </div>
    </section>
  );
}

// --- c) Boldest calls ---------------------------------------------------------------------------

export async function BoldestCalls() {
  const { fixtures, md } = await loadUpcoming();
  const calls = boldestCalls(fixtures);
  if (md === null || !calls.length) {
    return (
      <EmptyState title="No predictions for the next matchday yet">
        Predictions appear once the fixtures are confirmed.
      </EmptyState>
    );
  }
  return (
    <div
      role="region"
      aria-label="The model's boldest calls, scrollable"
      tabIndex={0}
      className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pt-1 pb-4 sm:-mx-6 sm:px-6"
    >
      {calls.map((m) => {
        const side = favouriteSide(m.prediction);
        const fav = side === "H" ? m.home : m.away;
        const p = side === "H" ? m.prediction.pHome : m.prediction.pAway;
        const { background, text } = badgeColors(fav);
        return (
          <Link
            key={m.id}
            href={`/matches/${md}`}
            className="flex w-[300px] shrink-0 snap-start overflow-hidden rounded-xl border border-line bg-midnight transition duration-150 hover:-translate-y-0.5 hover:border-floodlight focus-visible:-translate-y-0.5 focus-visible:border-floodlight motion-reduce:transition-none motion-reduce:hover:translate-y-0 motion-reduce:focus-visible:translate-y-0"
          >
            <span
              aria-hidden
              className="flex w-[84px] shrink-0 items-center justify-center font-score text-[26px] font-bold"
              style={{ backgroundColor: background, color: text }}
            >
              {displayCode(fav)}
            </span>
            <span className="flex min-w-0 flex-col p-4">
              <LocalTime
                iso={m.kickoff}
                format="dayTime"
                className="text-xs text-mist"
              />
              <span className="mt-1 truncate text-sm font-medium">
                {teamName(m.home)} v {teamName(m.away)}
              </span>
              <span className="mt-2 font-score text-5xl leading-none font-bold">
                {formatPct(p)}
              </span>
              <span className="mt-1 truncate text-sm text-mist">
                for {teamName(fav)}
              </span>
            </span>
          </Link>
        );
      })}
    </div>
  );
}

// --- d) Race for the trophy ---------------------------------------------------------------------

export async function RaceSection() {
  await connection();
  const race = await safely(getTitleRace);
  if (!race?.teams.length) {
    return (
      <EmptyState title="No title odds yet">
        The season has not been simulated yet.
      </EmptyState>
    );
  }
  const caption = `${race.nSims.toLocaleString("en-GB")} simulated seasons · results through ${formatDate(race.resultsThrough)}`;
  return <Race teams={race.teams} caption={caption} />;
}

// --- e) Report card -----------------------------------------------------------------------------

export async function ReportCard() {
  await connection();
  const season = await safely(getCurrentSeason);
  if (!season) return null;
  const [matches, scored] = await Promise.all([
    safely(getSeasonMatches),
    safely(() => getScoredPredictions(season)),
  ]);
  if (!matches || !scored?.length) return null;
  const md = lastCompletedMatchday(matches, scored);
  const card = md === null ? null : reportCard(scored, md);
  if (!card) return null;

  return (
    <section aria-labelledby="report-card">
      <h2 id="report-card" className={sectionTitle}>
        Matchday {card.matchday} report card
      </h2>
      <div className="mt-5 grid gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] md:items-start">
        <div>
          <p className="font-score leading-none font-bold">
            <span className="text-[80px]">{card.hits}</span>
            <span className="text-[44px] text-muted"> / {card.n}</span>
          </p>
          <p className="mt-3 max-w-[40ch] text-mist">
            favourites came through. Log loss {card.logLoss.toFixed(3)},{" "}
            {formatPct(Math.abs(card.gain), 1)}{" "}
            {card.gain >= 0 ? "better" : "worse"} than guessing.
          </p>
          <p className="mt-3">
            <Link href="/accuracy" className={inlineLink}>
              See every prediction
            </Link>
          </p>
        </div>
        <div>
          <div className="grid max-w-[30rem] grid-cols-6 gap-2 sm:grid-cols-9">
            {card.dots.map((d) => (
              <span
                key={d.matchId}
                role="img"
                aria-label={d.label}
                title={d.label}
                className={cn(
                  "flex aspect-square w-full max-w-10 items-center justify-center rounded-full text-lg font-bold",
                  d.hit ? "bg-floodlight text-night" : "border-2",
                )}
                style={d.hit ? undefined : { borderColor: MISS, color: MISS }}
              >
                <span aria-hidden>{d.hit ? "✓" : "✗"}</span>
              </span>
            ))}
          </div>
          <p className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm text-mist">
            <span className="flex items-center gap-2">
              <span
                aria-hidden
                className="flex size-6 items-center justify-center rounded-full bg-floodlight text-sm font-bold text-night"
              >
                ✓
              </span>
              Favourite won
            </span>
            <span className="flex items-center gap-2">
              <span
                aria-hidden
                className="flex size-6 items-center justify-center rounded-full border-2 text-sm font-bold"
                style={{ borderColor: MISS, color: MISS }}
              >
                ✗
              </span>
              Upset
            </span>
          </p>
        </div>
      </div>
    </section>
  );
}
