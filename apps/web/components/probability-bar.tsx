import { cn } from "@/lib/utils";
import { formatPct } from "@/lib/data/derive";

/** Home / draw / away as three segments with 2px gaps. */
export function ProbabilityBar({
  pHome,
  pDraw,
  pAway,
  homeName,
  awayName,
  homeColor,
  awayColor,
  className,
}: {
  pHome: number;
  pDraw: number;
  pAway: number;
  homeName: string;
  awayName: string;
  homeColor: string;
  awayColor: string;
  className?: string;
}) {
  const label = `${homeName} ${formatPct(pHome)}, draw ${formatPct(pDraw)}, ${awayName} ${formatPct(pAway)}`;
  const segment = "h-full min-w-[2px] rounded-[1px]";
  // Same inset ring as TeamBadge, so near-black club colours stay visible on the night background.
  const team = cn(segment, "ring-1 ring-white/18 ring-inset");
  return (
    <div
      role="img"
      aria-label={label}
      className={cn("flex h-2 w-full gap-[2px]", className)}
    >
      <span
        className={team}
        style={{ flex: `${pHome} 1 0%`, backgroundColor: homeColor }}
      />
      <span
        className={cn(segment, "bg-draw")}
        style={{ flex: `${pDraw} 1 0%` }}
      />
      <span
        className={team}
        style={{ flex: `${pAway} 1 0%`, backgroundColor: awayColor }}
      />
    </div>
  );
}
