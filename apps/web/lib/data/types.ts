// Plain, serialisable shapes returned by lib/data (safe to pass to client components).

export type TeamRef = {
  id: number; // internal teams.id: differs between databases
  fdId: number | null; // football-data team id: stable, keys lib/teams/display
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
  rps: number;
  accuracy: number;
  uniformLogLoss: number;
  uniformRps: number;
  uniformAccuracy: number;
  isPrimary: boolean;
};

export type Outcome = "H" | "D" | "A";

/** One official (pre-kick-off) prediction of a finished match, scored on the 90-minute result. */
export type ScoredPrediction = {
  matchId: number;
  model: string;
  stage: string;
  matchday: number | null;
  kickoff: string; // ISO UTC
  home: TeamRef;
  away: TeamRef;
  homeGoals: number;
  awayGoals: number;
  outcome: Outcome;
  predicted: Outcome;
  pHome: number;
  pDraw: number;
  pAway: number;
  logLoss: number;
  rps: number;
  hit: boolean;
};

export type CalibrationBin = {
  lo: number;
  hi: number;
  n: number;
  meanPred: number | null;
  observed: number | null;
};

export type BacktestRow = {
  model: string;
  role: "candidate" | "baseline";
  scope: string; // a test season label, or "overall"
  n: number;
  logLoss: number;
  rps: number;
  brier: number;
  accuracy: number;
  isPrimary: boolean;
};

export type Backtest = {
  rows: BacktestRow[];
  /** The primary model's test-season calibration; away is null when the run did not store it. */
  calibration: {
    model: string;
    home: CalibrationBin[] | null;
    away: CalibrationBin[] | null;
  } | null;
};
