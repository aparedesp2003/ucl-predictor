import { cn } from "@/lib/utils";
import { teamColors } from "@/lib/teams/colors";
import type { TeamRef } from "@/lib/data/types";

const SIZES = {
  sm: "size-6 text-[9px]",
  md: "size-8 text-[11px]",
  lg: "size-11 text-sm",
} as const;

function initials(team: Pick<TeamRef, "tla" | "name">): string {
  if (team.tla) return team.tla;
  return team.name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
}

/** Initials in the club's colours. Decorative: the team name is always shown next to it. */
export function TeamBadge({
  team,
  size = "md",
  color,
  className,
}: {
  team: Pick<TeamRef, "tla" | "name">;
  size?: keyof typeof SIZES;
  color?: string; // override the background (e.g. the away side's clash colour)
  className?: string;
}) {
  const colors = teamColors(team);
  const background = color ?? colors.primary;
  const text =
    background === colors.primary
      ? colors.onPrimary
      : bestText(background, colors.primary);
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
      {initials(team)}
    </span>
  );
}

function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

// On the secondary colour, use the primary if it reads well, otherwise black or white.
function bestText(background: string, primary: string): string {
  const contrast = (a: string, b: string) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };
  if (contrast(background, primary) >= 4.5) return primary;
  return contrast(background, "#FFFFFF") >= contrast(background, "#111111")
    ? "#FFFFFF"
    : "#111111";
}
