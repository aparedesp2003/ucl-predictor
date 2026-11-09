import { cn } from "@/lib/utils";
import { badgeColors } from "@/lib/teams/colors";
import { displayCode } from "@/lib/teams/display";
import type { TeamRef } from "@/lib/data/types";

const SIZES = {
  sm: "size-6 text-[9px]",
  md: "size-8 text-[11px]",
  lg: "size-11 text-sm",
} as const;

/** Initials in the club's colours. Decorative: the team name is always shown next to it. */
export function TeamBadge({
  team,
  size = "md",
  color,
  className,
}: {
  team: Pick<TeamRef, "fdId" | "tla" | "name">;
  size?: keyof typeof SIZES;
  color?: string; // override the background (e.g. the away side's clash colour)
  className?: string;
}) {
  const { background, text } = badgeColors(team, color);
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold tracking-tight ring-1 ring-white/18 ring-inset",
        SIZES[size],
        className,
      )}
      style={{ backgroundColor: background, color: text }}
    >
      {displayCode(team)}
    </span>
  );
}
