// Cache tags for lib/data reads. POST /api/revalidate expires all of them after a pipeline run.
export const CACHE_TAGS = [
  "matches",
  "odds",
  "scoreboard",
  "backtest",
] as const;

export type CacheTag = (typeof CACHE_TAGS)[number];
