// Plain, serialisable shapes returned by lib/data (safe to pass to client components).

export type TeamRef = {
  id: number;
  name: string;
  shortName: string | null;
  tla: string | null;
};

export type Prediction = {
  pHome: number;
  pDraw: number;
  pAway: number;
  model: string;
  predictedAt: string; // ISO UTC
};

export type MatchRow = {
  id: number;
  season: string;
  stage: string;
  matchday: number | null;
  leg: number | null;
  kickoff: string; // ISO UTC; midnight UTC of match_date when the kick-off time is unknown
  status: string;
  homeGoals: number | null;
  awayGoals: number | null;
  home: TeamRef;
  away: TeamRef;
  prediction: Prediction | null;
};

export type TitleOdds = {
  team: TeamRef;
  pTop8: number;
  pPlayoff: number;
  pOut: number;
  pR16: number;
  pQf: number;
  pSf: number;
  pFinal: number;
  pWin: number;
  expectedPoints: number;
};

export type TitleRace = {
  season: string;
  nSims: number;
  runCreatedAt: string; // ISO UTC
  resultsThrough: string; // YYYY-MM-DD
  teams: TitleOdds[]; // sorted by pWin, highest first
};

export type ScoreRow = {
  model: string;
  season: string;
  n: number;
  logLoss: number;
  uniformLogLoss: number;
  accuracy: number;
  isPrimary: boolean;
};

export type Outcome = "H" | "D" | "A";
