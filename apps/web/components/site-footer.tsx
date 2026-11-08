import { GITHUB_URL } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-line">
      <div className="mx-auto max-w-6xl space-y-1 px-4 py-6 text-sm text-mist sm:px-6">
        <p>Independent fan project. Not affiliated with UEFA or any club.</p>
        <p>
          Match data from{" "}
          <a
            className="text-floodlight hover:underline"
            href="https://www.football-data.org/"
          >
            football-data.org
          </a>{" "}
          and{" "}
          <a
            className="text-floodlight hover:underline"
            href="https://github.com/openfootball"
          >
            openfootball
          </a>
          . Source code on{" "}
          <a className="text-floodlight hover:underline" href={GITHUB_URL}>
            GitHub
          </a>
          .
        </p>
      </div>
    </footer>
  );
}
