// Read-only mirror of the views apps/engine creates for the web (Alembic migrations
// 5c2e7a91d4b3_week5_web_views and e6a1c4d27f90_week6_web_accuracy_views; the fd_team_id columns
// come from f3d81a6c2b57_week7_web_views_fd_team_id). They are the only
// relations the web role can read.
// Hand-written and marked .existing(): never run drizzle-kit push/migrate/generate.
import {
  bigint,
  boolean,
  date,
  doublePrecision,
  integer,
  jsonb,
  numeric,
  pgView,
  smallint,
  timestamp,
  varchar,
} from "drizzle-orm/pg-core";

export const webMatchPredictions = pgView("web_match_predictions", {
  matchId: integer("match_id").notNull(),
  season: varchar("season", { length: 7 }).notNull(),
  stage: varchar("stage", { length: 32 }).notNull(),
  matchday: smallint("matchday"),
  leg: smallint("leg"),
  kickoffUtc: timestamp("kickoff_utc", { withTimezone: true }),
  matchDate: date("match_date").notNull(),
  status: varchar("status", { length: 32 }).notNull(),
  homeGoals90: smallint("home_goals_90"),
  awayGoals90: smallint("away_goals_90"),
  homeTeamId: integer("home_team_id").notNull(),
  homeName: varchar("home_name", { length: 128 }).notNull(),
  homeShortName: varchar("home_short_name", { length: 64 }),
  homeTla: varchar("home_tla", { length: 8 }),
  awayTeamId: integer("away_team_id").notNull(),
  awayName: varchar("away_name", { length: 128 }).notNull(),
  awayShortName: varchar("away_short_name", { length: 64 }),
  awayTla: varchar("away_tla", { length: 8 }),
  pHome: doublePrecision("p_home"),
  pDraw: doublePrecision("p_draw"),
  pAway: doublePrecision("p_away"),
  model: varchar("model", { length: 32 }),
  predictedAt: timestamp("predicted_at", { withTimezone: true }),
  homeFdTeamId: integer("home_fd_team_id"),
  awayFdTeamId: integer("away_fd_team_id"),
}).existing();

export const webTitleOdds = pgView("web_title_odds", {
  season: varchar("season", { length: 7 }).notNull(),
  simulationRunId: integer("simulation_run_id").notNull(),
  teamId: integer("team_id").notNull(),
  name: varchar("name", { length: 128 }).notNull(),
  shortName: varchar("short_name", { length: 64 }),
  tla: varchar("tla", { length: 8 }),
  pTop8: doublePrecision("p_top8").notNull(),
  pPlayoff: doublePrecision("p_playoff").notNull(),
  pOut: doublePrecision("p_out").notNull(),
  pR16: doublePrecision("p_r16").notNull(),
  pQf: doublePrecision("p_qf").notNull(),
  pSf: doublePrecision("p_sf").notNull(),
  pFinal: doublePrecision("p_final").notNull(),
  pWin: doublePrecision("p_win").notNull(),
  expectedPoints: doublePrecision("expected_points").notNull(),
  nSims: integer("n_sims").notNull(),
  runCreatedAt: timestamp("run_created_at", { withTimezone: true }).notNull(),
  resultsThrough: date("results_through").notNull(),
  fdTeamId: integer("fd_team_id"),
}).existing();

// avg() of an integer expression is numeric in Postgres; avg() of float8 stays float8.
export const webModelScoreboard = pgView("web_model_scoreboard", {
  model: varchar("model", { length: 32 }).notNull(),
  season: varchar("season", { length: 7 }).notNull(),
  n: bigint("n", { mode: "number" }).notNull(),
  logLoss: doublePrecision("log_loss").notNull(),
  rps: doublePrecision("rps").notNull(),
  brier: doublePrecision("brier").notNull(),
  accuracy: numeric("accuracy", { mode: "number" }).notNull(),
  uniformLogLoss: doublePrecision("uniform_log_loss").notNull(),
  uniformRps: doublePrecision("uniform_rps").notNull(),
  uniformBrier: doublePrecision("uniform_brier").notNull(),
  uniformAccuracy: numeric("uniform_accuracy", { mode: "number" }).notNull(),
  isPrimary: boolean("is_primary").notNull(),
}).existing();

// Migration e6a1c4d27f90_week6_web_accuracy_views.
export const webPredictionScores = pgView("web_prediction_scores", {
  model: varchar("model", { length: 32 }).notNull(),
  matchId: integer("match_id").notNull(),
  season: varchar("season", { length: 7 }).notNull(),
  stage: varchar("stage", { length: 32 }).notNull(),
  matchday: smallint("matchday"),
  kickoffUtc: timestamp("kickoff_utc", { withTimezone: true }),
  matchDate: date("match_date").notNull(),
  homeTeamId: integer("home_team_id").notNull(),
  homeName: varchar("home_name", { length: 128 }).notNull(),
  homeShortName: varchar("home_short_name", { length: 64 }),
  homeTla: varchar("home_tla", { length: 8 }),
  awayTeamId: integer("away_team_id").notNull(),
  awayName: varchar("away_name", { length: 128 }).notNull(),
  awayShortName: varchar("away_short_name", { length: 64 }),
  awayTla: varchar("away_tla", { length: 8 }),
  homeGoals90: smallint("home_goals_90").notNull(),
  awayGoals90: smallint("away_goals_90").notNull(),
  outcome: varchar("outcome", { length: 1 }).notNull(),
  predicted: varchar("predicted", { length: 1 }).notNull(),
  pHome: doublePrecision("p_home").notNull(),
  pDraw: doublePrecision("p_draw").notNull(),
  pAway: doublePrecision("p_away").notNull(),
  logLoss: doublePrecision("log_loss").notNull(),
  rps: doublePrecision("rps").notNull(),
  brier: doublePrecision("brier").notNull(),
  hit: boolean("hit").notNull(),
  isPrimary: boolean("is_primary").notNull(),
  homeFdTeamId: integer("home_fd_team_id"),
  awayFdTeamId: integer("away_fd_team_id"),
}).existing();

// Calibration bins ({lo, hi, n, mean_pred, observed}) are only set on the 'overall' rows.
export const webBacktestSummary = pgView("web_backtest_summary", {
  model: varchar("model", { length: 32 }).notNull(),
  role: varchar("role", { length: 16 }).notNull(),
  modelRunId: integer("model_run_id").notNull(),
  runCreatedAt: timestamp("run_created_at", { withTimezone: true }).notNull(),
  scope: varchar("scope", { length: 16 }).notNull(),
  n: integer("n").notNull(),
  logLoss: doublePrecision("log_loss").notNull(),
  rps: doublePrecision("rps").notNull(),
  brier: doublePrecision("brier").notNull(),
  accuracy: doublePrecision("accuracy").notNull(),
  isPrimary: boolean("is_primary").notNull(),
  calibrationHome: jsonb("calibration_home").$type<RawCalibrationBin[]>(),
  calibrationAway: jsonb("calibration_away").$type<RawCalibrationBin[]>(),
}).existing();

export type RawCalibrationBin = {
  lo: number;
  hi: number;
  n: number;
  mean_pred: number | null;
  observed: number | null;
};
