// Visitor-facing team names and badge codes, keyed by football-data team id (fd_team_id), which is
// the same in every database. football-data's own short names and TLAs are inconsistent
// ("Shaktar", "Sl. Bratislava", Barcelona and Bayern both "FCB", Bodø/Glimt "FK"), so the clubs of
// the current league phase get a short common English name and a 3-letter code that is unique
// within the competition. Anyone else falls back to the DB short_name / tla.
//
// Colours are not keyed here: lib/teams/colors resolves them from the DB tla and name as before.

export type TeamDisplay = { name: string; code: string };

type DisplayTeam = {
  fdId: number | null;
  name: string;
  shortName?: string | null;
  tla: string | null;
};

const d = (name: string, code: string): TeamDisplay => ({ name, code });

export const TEAM_DISPLAY: Record<number, TeamDisplay> = {
  4: d("Dortmund", "BVB"),
  5: d("Bayern", "FCB"),
  10: d("Stuttgart", "VFB"),
  57: d("Arsenal", "ARS"),
  58: d("Aston Villa", "AVL"),
  64: d("Liverpool", "LIV"),
  65: d("Man City", "MCI"),
  66: d("Man United", "MUN"),
  78: d("Atlético", "ATL"),
  81: d("Barcelona", "BAR"),
  86: d("Real Madrid", "RMA"),
  90: d("Real Betis", "BET"),
  94: d("Villarreal", "VIL"),
  100: d("Roma", "ROM"),
  108: d("Inter", "INT"),
  113: d("Napoli", "NAP"),
  498: d("Sporting CP", "SCP"),
  503: d("Porto", "POR"),
  521: d("Lille", "LIL"),
  524: d("PSG", "PSG"),
  546: d("Lens", "LEN"),
  610: d("Galatasaray", "GAL"),
  613: d("Fenerbahçe", "FEN"),
  674: d("PSV", "PSV"),
  675: d("Feyenoord", "FEY"),
  721: d("RB Leipzig", "RBL"),
  851: d("Club Brugge", "BRU"),
  930: d("Slavia Prague", "SLA"),
  1887: d("Shakhtar", "SHA"),
  1899: d("AEK", "AEK"),
  2016: d("LASK", "LAS"),
  5720: d("Viking", "VIK"),
  5721: d("Bodø/Glimt", "BOD"),
  7397: d("Como", "COM"),
  7509: d("Slovan Bratislava", "SLO"),
  10233: d("Sabah", "SAB"),
};

function entry(team: DisplayTeam): TeamDisplay | undefined {
  return team.fdId === null ? undefined : TEAM_DISPLAY[team.fdId];
}

export function displayName(team: DisplayTeam): string {
  return entry(team)?.name ?? team.shortName ?? team.name;
}

export function displayCode(team: DisplayTeam): string {
  const known = entry(team);
  if (known) return known.code;
  if (team.tla) return team.tla;
  return team.name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
}
