import { FileText, Flag, Lock, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { ArenaMark } from "@/components/brand/arena-mark";
import { getBacktest, getCurrentSeason } from "@/lib/data/accuracy";
import { getTitleRace } from "@/lib/data/odds";
import { safely } from "@/lib/data/safe";
import { simsInWords } from "@/lib/data/scorecard";
import { getScoreboard } from "@/lib/data/scoreboard";
import { GITHUB_URL, pageMetadata } from "@/lib/site";

import { Timeline, type TimelineStep } from "./timeline";

export const metadata: Metadata = pageMetadata({
  title: "About",
  description:
    "How the Champions League predictions are made, locked before kick-off and scored, where the data comes from, and what the model cannot know.",
  path: "/about",
});

const DEFAULT_SIMS = 10_000;
const BACKTEST_N = 753;
const MATCHES = "2,250+";
const UPSET = "#F5A35C";

const kicker = "text-sm font-medium tracking-wide text-floodlight uppercase";
const h2 = "font-display text-3xl font-semibold";
const link =
  "text-floodlight underline decoration-floodlight/40 underline-offset-2 hover:decoration-floodlight";

// The live numbers are read at request time; everything else is static.
async function loadFacts() {
  await connection();
  const [race, season, backtest] = await Promise.all([
    safely(getTitleRace),
    safely(getCurrentSeason),
    safely(getBacktest),
  ]);
  const scores = season ? await safely(() => getScoreboard(season)) : null;
  return {
    nSims: race?.nSims ?? DEFAULT_SIMS,
    liveN: scores?.find((s) => s.isPrimary)?.n ?? 0,
    backtestN:
      backtest?.rows.find((r) => r.scope === "overall")?.n ?? BACKTEST_N,
  };
}

function steps(nSims: number): TimelineStep[] {
  return [
    {
      minute: "0'",
      title: "The data",
      text: `Every Champions League match since 2011-12, over ${MATCHES.replace("+", "")} of them, from openfootball and football-data.org, with every club matched across both sources.`,
    },
    {
      minute: "15'",
      title: "Ratings",
      text: "Each club has an Elo rating. Every result nudges both teams, bigger wins move them more, and ratings drift back toward average between seasons.",
    },
    {
      minute: "30'",
      title: "Chances",
      text: "The rating gap, plus home advantage, becomes a home win, draw and away win probability for every fixture.",
    },
    {
      minute: "45'",
      title: "Scorelines",
      text: "A Poisson goals model turns the same gap into expected goals, so every possible scoreline gets a probability too.",
    },
    {
      minute: "60'",
      title: "Simulation",
      text: `The rest of the season is played ${nSims.toLocaleString("en-GB")} times under the 2026/27 rules, with uncertainty in every rating, to find each club's chance of every round.`,
    },
    {
      minute: "75'",
      title: "Locked",
      text: "Each prediction is stamped by the database clock before kick-off. After that it can never be changed.",
    },
    {
      minute: "90'",
      title: "Full time",
      text: "Once the result is in, every locked prediction is scored on the 90-minute result, in public, next to plain guessing.",
    },
  ];
}

const HONEST = [
  {
    icon: Lock,
    title: "Locked before kick-off",
    text: "Every prediction is stamped by the database clock, and only those made before kick-off count.",
  },
  {
    icon: FileText,
    title: "Never edited",
    text: "Predictions are only ever added. None is changed or deleted once saved, and the official one is the latest before kick-off.",
  },
  {
    icon: Flag,
    title: "Rules set in advance",
    text: "The main model was picked by a rule written down beforehand, the lowest log loss on validation seasons, and nothing was tuned on the test seasons.",
  },
  {
    icon: ShieldCheck,
    title: "Read-only site",
    text: "This site connects with a role that can only read the published results, so it has no way to change a prediction.",
  },
];

const STACK = [
  "Python",
  "pandas",
  "SciPy",
  "scikit-learn",
  "PostgreSQL",
  "Alembic",
  "GitHub Actions",
  "Next.js",
  "TypeScript",
  "Tailwind CSS",
  "Vercel",
];

async function HeroTitle() {
  const { nSims } = await loadFacts();
  return <>Ninety minutes, {simsInWords(nSims)} seasons</>;
}

function Numbers({ nSims }: { nSims: number }) {
  const cells = [
    { value: MATCHES, label: "matches since 2011-12" },
    { value: "15", label: "seasons of history" },
    {
      value: nSims.toLocaleString("en-GB"),
      label: "seasons simulated each run",
    },
    { value: "06:15", label: "UTC, refreshed every morning" },
  ];
  return (
    <dl className="grid grid-cols-2 overflow-hidden rounded-[20px] border border-line md:grid-cols-4">
      {cells.map((c, i) => (
        <div
          key={c.label}
          className={
            "flex flex-col-reverse justify-end gap-1 border-line bg-midnight p-5 sm:p-6 " +
            (i % 2 === 1 ? "border-l " : "") +
            (i >= 2 ? "border-t md:border-t-0 " : "") +
            (i === 2 ? "md:border-l" : "")
          }
        >
          <dt className="text-sm text-mist">{c.label}</dt>
          <dd className="font-score text-[44px] leading-none font-bold sm:text-[56px]">
            {c.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

async function LiveNumbers() {
  const { nSims } = await loadFacts();
  return <Numbers nSims={nSims} />;
}

async function LiveTimeline() {
  const { nSims } = await loadFacts();
  return <Timeline steps={steps(nSims)} />;
}

async function SmallSample() {
  const { liveN, backtestN } = await loadFacts();
  return (
    <>
      {liveN > 0
        ? `${liveN.toLocaleString("en-GB")} matches scored so far this season, against the ${backtestN.toLocaleString("en-GB")}-match backtest, so the live numbers will swing for a while.`
        : `No matches scored yet this season. Until then, the ${backtestN.toLocaleString("en-GB")}-match backtest is the guide.`}
    </>
  );
}

export default function AboutPage() {
  const unknowns = [
    {
      title: "Champions League only",
      text: "Ratings never see domestic leagues, injuries, transfers or rotation.",
    },
    {
      title: "Frozen mid-simulation",
      text: "Each simulated season draws its rating noise once, so a club that improves through the winter is not modelled.",
    },
    {
      title: "Last year's bracket",
      text: "The knockout draw follows the 2025/26 procedure until the 2026/27 one is published.",
    },
    {
      title: "Small sample",
      text: (
        <Suspense
          fallback={`A season is a few hundred matches at most; the ${BACKTEST_N}-match backtest is the steadier guide.`}
        >
          <SmallSample />
        </Suspense>
      ),
    },
  ];

  return (
    <main id="main" className="mx-auto max-w-6xl space-y-20 px-4 py-12 sm:px-6">
      <section
        aria-labelledby="about-title"
        className="grid items-center gap-8 md:grid-cols-[auto_minmax(0,1fr)] md:gap-12"
      >
        <ArenaMark className="w-44 md:w-[260px]" />
        <div>
          <p className={kicker}>About Ninety</p>
          <h1
            id="about-title"
            className="mt-3 font-display text-4xl leading-tight font-semibold md:text-6xl"
          >
            <Suspense fallback="Ninety minutes, ten thousand seasons">
              <HeroTitle />
            </Suspense>
          </h1>
          <p className="mt-5 max-w-[55ch] text-lg text-mist">
            A Champions League prediction model that shows its working: every
            forecast is locked before kick-off and marked in public afterwards.
          </p>
        </div>
      </section>

      <section aria-label="Ninety in numbers">
        <Suspense fallback={<Numbers nSims={DEFAULT_SIMS} />}>
          <LiveNumbers />
        </Suspense>
      </section>

      <section aria-labelledby="timeline">
        <h2 id="timeline" className={h2}>
          From kick-off to final whistle
        </h2>
        <p className="mt-2 mb-8 max-w-[65ch] text-mist">
          How a fixture becomes a prediction, in seven steps. Pick a minute.
        </p>
        <Suspense fallback={<Timeline steps={steps(DEFAULT_SIMS)} />}>
          <LiveTimeline />
        </Suspense>
      </section>

      <section aria-labelledby="honest">
        <h2 id="honest" className={h2}>
          Honest by design
        </h2>
        <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {HONEST.map(({ icon: Icon, title, text }) => (
            <li
              key={title}
              className="rounded-[20px] border border-line bg-midnight p-6"
            >
              <Icon
                aria-hidden
                className="size-7 text-floodlight"
                strokeWidth={1.75}
              />
              <h3 className="mt-4 font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-mist">{text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="unknowns">
        <h2 id="unknowns" className={h2}>
          Known unknowns
        </h2>
        <ul className="mt-6 grid gap-x-10 gap-y-6 sm:grid-cols-2">
          {unknowns.map((u) => (
            <li key={u.title} className="border-l-2 border-line pl-5">
              <h3
                className="font-score text-xl font-bold tracking-wide uppercase"
                style={{ color: UPSET }}
              >
                {u.title}
              </h3>
              <p className="mt-1 text-mist">{u.text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section
        aria-labelledby="author"
        className="rounded-[20px] border border-line bg-midnight p-6 sm:p-10"
      >
        <h2 id="author" className={h2}>
          Built by Andres Paredes
        </h2>
        <p className="mt-3 max-w-[60ch] text-lg text-mist">
          Full-stack developer in Toronto. I built Ninety end to end: the data
          pipeline, the models, the daily automation and this site.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a
            href="https://andresparedesp.dev"
            className="inline-flex min-h-11 items-center rounded-full bg-floodlight px-5 font-semibold text-night hover:bg-starlight"
          >
            Portfolio
          </a>
          <a
            href={GITHUB_URL}
            className="inline-flex min-h-11 items-center rounded-full border-2 border-floodlight px-5 font-semibold text-floodlight hover:bg-floodlight/10"
          >
            Source on GitHub
          </a>
        </div>
        <ul aria-label="Tech stack" className="mt-6 flex flex-wrap gap-2">
          {STACK.map((s) => (
            <li
              key={s}
              className="rounded-full border border-line px-3 py-1 text-sm text-silver"
            >
              {s}
            </li>
          ))}
        </ul>
        <div className="mt-8 space-y-2 border-t border-line pt-6 text-sm text-mist">
          <p>
            Fixtures and results for the current season from{" "}
            <a href="https://www.football-data.org/" className={link}>
              football-data.org
            </a>
            ; Champions League results back to 2011-12 from{" "}
            <a href="https://github.com/openfootball" className={link}>
              openfootball
            </a>
            , open football data in the public domain. How the predictions score
            is on the{" "}
            <Link href="/accuracy" className={link}>
              accuracy page
            </Link>
            .
          </p>
          <p>
            Not affiliated with, endorsed by or connected to UEFA or any club.
            Club names are used only to identify teams.
          </p>
        </div>
      </section>
    </main>
  );
}
