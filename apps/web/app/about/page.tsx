import type { Metadata } from "next";
import Link from "next/link";

import { GITHUB_URL, pageMetadata } from "@/lib/site";

export const metadata: Metadata = pageMetadata({
  title: "About",
  description:
    "How the Champions League predictions are made, locked before kick-off and scored, where the data comes from, and what the model cannot know.",
  path: "/about",
});

const h2 = "mt-12 font-display text-2xl font-semibold";
const link =
  "text-floodlight underline decoration-floodlight/40 underline-offset-2 hover:decoration-floodlight";

export default function AboutPage() {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <article className="max-w-[70ch] text-left leading-relaxed">
        <p className="text-sm font-medium tracking-wide text-floodlight uppercase">
          About
        </p>
        <h1 className="mt-2 font-display text-4xl font-semibold">
          How the predictions work
        </h1>
        <p className="mt-4 text-mist">
          Ninety gives a home, draw and away probability for every Champions
          League match before it kicks off, keeps score of how those
          probabilities hold up, and plays out the rest of the season to
          estimate where each club will finish.
        </p>

        <section aria-labelledby="method">
          <h2 id="method" className={h2}>
            The method
          </h2>
          <div className="mt-4 space-y-4">
            <p>
              <strong className="font-semibold">Ratings.</strong> Every club has
              an Elo rating built from every Champions League match since
              2011-12, qualifiers included. Beating a stronger side earns more
              points than beating a weaker one, and ratings drift back towards
              the average between seasons.
            </p>
            <p>
              <strong className="font-semibold">Outcomes.</strong> The rating
              gap between two clubs, with an allowance for home advantage, turns
              into a probability of a home win, a draw and an away win.
            </p>
            <p>
              <strong className="font-semibold">Scorelines.</strong> A Poisson
              goals model turns the same gap into expected goals for each side,
              which gives the chance of every scoreline. The simulator needs
              those to break ties on goal difference.
            </p>
            <p>
              <strong className="font-semibold">The season.</strong> The
              remaining fixtures are played out thousands of times, each with a
              little random noise in the ratings to reflect what the model does
              not know. Counting where each club finished across those runs
              gives its chance of the top 8, the play-offs, each knockout round
              and the title.
            </p>
            <p>
              Several candidate models were compared on past seasons. The one
              used on this site was picked by a rule fixed in advance: the
              lowest log loss on earlier validation seasons, kept only if it is
              no worse than plain Elo on the later test seasons. Nothing was
              tuned on the test seasons.
            </p>
          </div>
        </section>

        <section aria-labelledby="locking">
          <h2 id="locking" className={h2}>
            How predictions are locked and scored
          </h2>
          <div className="mt-4 space-y-4">
            <p>
              Predictions are refreshed every morning. The last one saved before
              kick-off is the official prediction; after kick-off it is never
              edited or deleted, and nothing saved later counts.
            </p>
            <p>
              Each official prediction is scored on the 90-minute result, so
              extra time and penalties do not change it. The{" "}
              <Link href="/accuracy" className={link}>
                accuracy page
              </Link>{" "}
              reports log loss, which rewards confident calls that come true and
              punishes confident calls that do not, and RPS, which also credits
              a near miss. Both are compared with guessing a third for each
              outcome.
            </p>
          </div>
        </section>

        <section aria-labelledby="data">
          <h2 id="data" className={h2}>
            Data sources
          </h2>
          <ul className="mt-4 list-disc space-y-2 pl-5">
            <li>
              Fixtures and results for the current season from{" "}
              <a href="https://www.football-data.org/" className={link}>
                football-data.org
              </a>
              .
            </li>
            <li>
              Historical results back to 2011-12 from{" "}
              <a href="https://github.com/openfootball" className={link}>
                openfootball
              </a>
              , open football data in the public domain.
            </li>
          </ul>
        </section>

        <section aria-labelledby="limits">
          <h2 id="limits" className={h2}>
            Honest limitations
          </h2>
          <ul className="mt-4 list-disc space-y-3 pl-5">
            <li>
              <strong className="font-semibold">
                Champions League matches only.
              </strong>{" "}
              Ratings never see domestic leagues, so a club that is flying at
              home but rarely plays in Europe can be underrated, and injuries,
              transfers and rotation are invisible.
            </li>
            <li>
              <strong className="font-semibold">
                Ratings are frozen within a simulated season.
              </strong>{" "}
              Each simulated season adds noise once, then keeps ratings fixed; a
              club that improves through the winter is not modelled.
            </li>
            <li>
              <strong className="font-semibold">
                The knockout bracket is approximated.
              </strong>{" "}
              League positions and play-off rules follow the 2026/27
              regulations, but the knockout draw is simulated with the 2025/26
              procedure until the new one is confirmed.
            </li>
            <li>
              <strong className="font-semibold">
                The live sample is small.
              </strong>{" "}
              A season has a few hundred matches at most, so the live accuracy
              numbers swing a lot early on. The five-season backtest is the
              steadier guide.
            </li>
          </ul>
        </section>

        <section aria-labelledby="who">
          <h2 id="who" className={h2}>
            Who made this
          </h2>
          <div className="mt-4 space-y-4">
            <p>
              An independent project by{" "}
              <a href="https://andresparedesp.dev" className={link}>
                Andres Paredes
              </a>
              . The code, models and backtests are open on{" "}
              <a href={GITHUB_URL} className={link}>
                GitHub
              </a>
              .
            </p>
            <p className="text-mist">
              Not affiliated with, endorsed by or connected to UEFA or any club.
              Club names are used only to identify teams.
            </p>
          </div>
        </section>
      </article>
    </main>
  );
}
