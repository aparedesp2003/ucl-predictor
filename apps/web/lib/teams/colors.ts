// Club colours for the 2026-27 league phase, keyed by the TLAs football-data stores.
// APPROXIMATE, VERIFY: hand-picked hex values, not official brand colours. Entries marked
// "picked" were not in the original brief and are the most likely to need a check.

export type TeamColors = {
  primary: string;
  onPrimary: string; // text on primary
  secondary: string; // used for the away side when the primaries clash
};

const c = (
  primary: string,
  onPrimary: string,
  secondary: string,
): TeamColors => ({
  primary,
  onPrimary,
  secondary,
});

export const NEUTRAL_COLORS: TeamColors = c("#5B6694", "#FFFFFF", "#C9D1E3");

export const TEAM_COLORS: Record<string, TeamColors> = {
  PSG: c("#004170", "#FFFFFF", "#DA291C"),
  ARS: c("#EF0107", "#FFFFFF", "#063672"),
  FCB: c("#DC052D", "#FFFFFF", "#0066B2"), // Bayern München
  BAR: c("#A50044", "#FFFFFF", "#004D98"), // FC Barcelona (stored as FCB too, see colorKey)
  RMA: c("#FFFFFF", "#00529F", "#FEBE10"),
  LIV: c("#C8102E", "#FFFFFF", "#00B2A9"),
  MCI: c("#6CABDD", "#1C2C5B", "#1C2C5B"),
  AVL: c("#670E36", "#95BFE5", "#95BFE5"),
  ATL: c("#CB3524", "#FFFFFF", "#1B3F8B"), // Atlético (brief: ATM)
  INT: c("#0068A8", "#FFFFFF", "#111111"),
  BVB: c("#FDE100", "#111111", "#111111"),
  VIL: c("#FFE667", "#005187", "#005187"),
  AEK: c("#FFD200", "#111111", "#111111"), // picked
  BET: c("#00954C", "#FFFFFF", "#FFFFFF"), // picked
  BRU: c("#0067B1", "#FFFFFF", "#111111"), // picked
  COM: c("#1E4FA0", "#FFFFFF", "#FFFFFF"), // picked
  FCP: c("#00428C", "#FFFFFF", "#FFFFFF"), // picked
  FEN: c("#0A1F5C", "#FFED00", "#FFED00"), // picked
  FEY: c("#E2001A", "#FFFFFF", "#111111"), // picked
  FK: c("#FFD700", "#111111", "#111111"), // picked: Bodø/Glimt
  GAL: c("#A90432", "#FDB912", "#FDB912"), // picked
  LIL: c("#E01E13", "#FFFFFF", "#20325F"), // picked
  LIN: c("#111111", "#FFFFFF", "#FFFFFF"), // picked: LASK
  MUN: c("#DA291C", "#FFFFFF", "#FBE122"), // picked
  NAP: c("#12A0D7", "#FFFFFF", "#003C82"), // picked
  PSV: c("#ED1C24", "#FFFFFF", "#FFFFFF"), // picked
  RBL: c("#DD0741", "#FFFFFF", "#001F47"), // picked
  RCL: c("#D81E05", "#FFFFFF", "#FFD500"), // picked: Lens
  ROM: c("#8E1F2F", "#F0BC42", "#F0BC42"), // picked
  SAB: c("#F37021", "#111111", "#003B71"), // picked, least certain: Sabah FK
  SBA: c("#4A9FDB", "#0B1F44", "#0B1F44"), // picked: Slovan Bratislava
  SHD: c("#F37021", "#111111", "#111111"), // picked
  SLP: c("#E30613", "#FFFFFF", "#FFFFFF"), // picked: Slavia Praha
  SPO: c("#00804B", "#FFFFFF", "#FFFFFF"), // picked
  VFB: c("#FFFFFF", "#E32219", "#E32219"), // picked
  VIK: c("#00205B", "#FFFFFF", "#FFFFFF"), // picked: Viking
};

type TeamLike = { tla: string | null; name: string };

/** football-data gives FC Barcelona and Bayern München the same TLA (FCB). */
export function colorKey(team: TeamLike): string | null {
  if (team.tla === "FCB" && /barcel/i.test(team.name)) return "BAR";
  return team.tla;
}

export function teamColors(team: TeamLike): TeamColors {
  const key = colorKey(team);
  return (key && TEAM_COLORS[key]) || NEUTRAL_COLORS;
}

function rgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function rgbDistance(a: string, b: string): number {
  const [r1, g1, b1] = rgb(a);
  const [r2, g2, b2] = rgb(b);
  return Math.hypot(r1 - r2, g1 - g2, b1 - b2);
}

export const CLASH_DISTANCE = 130;

/** Home keeps its primary; the away side switches to its secondary when the primaries are close. */
export function clashColors(
  home: TeamLike,
  away: TeamLike,
): { home: string; away: string } {
  const h = teamColors(home);
  const a = teamColors(away);
  const clash = rgbDistance(h.primary, a.primary) < CLASH_DISTANCE;
  return { home: h.primary, away: clash ? a.secondary : a.primary };
}
