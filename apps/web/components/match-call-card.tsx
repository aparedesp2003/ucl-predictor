import { LocalTime } from "@/components/local-time";
import { LockedChip } from "@/components/locked-chip";
import { ProbabilityBar } from "@/components/probability-bar";
import { TeamBadge } from "@/components/team-badge";
import { favoured, formatPct, teamName } from "@/lib/data/derive";
import type { MatchRow, Prediction } from "@/lib/data/types";
import { clashColors } from "@/lib/teams/colors";
import { cn } from "@/lib/utils";

export function MatchCallCard({
  match,
  locked,
}: {
  match: MatchRow & { prediction: Prediction };
  locked: boolean;
}) {
  const { prediction: p, home, away } = match;
  const colors = clashColors(home, away);
  const pick = favoured(p);
  const tone = (side: "H" | "D" | "A") =>
    pick === side ? "font-semibold text-starlight" : "text-mist";

  return (
    <article className="rounded-md border border-line bg-midnight p-4">
      <div className="flex min-h-6 items-center justify-between gap-2 text-sm text-mist">
        <LocalTime iso={match.kickoff} format="dayTime" />
        {locked ? <LockedChip /> : null}
      </div>
      <h3 className="mt-3 space-y-2 text-starlight">
        <span className="flex items-center gap-2">
          <TeamBadge team={home} size="sm" color={colors.home} />
          {teamName(home)}
        </span>
        <span className="sr-only"> v </span>
        <span className="flex items-center gap-2">
          <TeamBadge team={away} size="sm" color={colors.away} />
          {teamName(away)}
        </span>
      </h3>
      <ProbabilityBar
        className="mt-4"
        pHome={p.pHome}
        pDraw={p.pDraw}
        pAway={p.pAway}
        homeName={teamName(home)}
        awayName={teamName(away)}
        homeColor={colors.home}
        awayColor={colors.away}
      />
      <dl className="mt-2 grid grid-cols-3 items-baseline">
        <div>
          <dt className="sr-only">{teamName(home)} win</dt>
          <dd className={cn("text-2xl", tone("H"))}>{formatPct(p.pHome)}</dd>
        </div>
        <div className="text-center text-sm">
          <dt className="inline text-mist">Draw </dt>
          <dd className={cn("inline", tone("D"))}>{formatPct(p.pDraw)}</dd>
        </div>
        <div className="text-right">
          <dt className="sr-only">{teamName(away)} win</dt>
          <dd className={cn("text-2xl", tone("A"))}>{formatPct(p.pAway)}</dd>
        </div>
      </dl>
    </article>
  );
}
