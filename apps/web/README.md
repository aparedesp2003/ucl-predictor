# apps/web

Next.js front end for the UCL predictor. It only **reads** the database, through five views that
`apps/engine` creates (migrations `5c2e7a91d4b3_week5_web_views` and
`e6a1c4d27f90_week6_web_accuracy_views`; `f3d81a6c2b57_week7_web_views_fd_team_id` adds the
football-data team ids):

| View                    | What it holds                                                                 |
| ----------------------- | ----------------------------------------------------------------------------- |
| `web_match_predictions` | Every match from 2026-27 on, with the official primary prediction             |
| `web_title_odds`        | Per team, the latest simulation of the current season                         |
| `web_model_scoreboard`  | Live log loss / RPS per model and season, with `is_primary`                   |
| `web_prediction_scores` | Per model and finished match from 2026-27 on: probabilities, scores and `hit` |
| `web_backtest_summary`  | Latest backtest per model: test metrics per season and overall, calibration   |

Pages: `/` (home), `/matches/[matchday]`, `/simulator`, `/accuracy`, `/about`.

Drizzle definitions for them are hand-written in `lib/db/schema.ts` (`pgView(...).existing()`).
Never run `drizzle-kit push`, `migrate` or `generate`: the schema belongs to the engine (Alembic).

## Environment

Locally these live in the repo-root `.env` (see `.env.example`); in production, in the hosting
platform's environment.

- `WEB_DATABASE_URL`: connection string for the `web_readonly` role. Required in production.
- `DATABASE_URL`: the engine's owner connection. In development only, the web falls back to it
  (with a console warning) when `WEB_DATABASE_URL` is empty.
- `REVALIDATE_SECRET`: shared secret for `POST /api/revalidate` (see [Live refresh](#live-refresh)).
  Unset means the endpoint rejects every request.
- `NEXT_PUBLIC_SITE_URL`: the public origin, e.g. `https://example.com`, used for `metadataBase`,
  `sitemap.xml` and `robots.txt`. Defaults to `http://localhost:3000`.

`pnpm --filter web build` needs no database: every data section reads at request time.

## The `web_readonly` role

A login role that can `SELECT` the five views above and nothing else. Creating it changes no
other role's privileges. Set it up once per database, as the database owner, with either script:

| Script                                 | Use it from                                   | Password                                                        |
| -------------------------------------- | --------------------------------------------- | --------------------------------------------------------------- |
| `docs/sql/web_readonly.sql`            | `psql`                                        | prompted (stays out of shell history), or `-v web_password=...` |
| `docs/sql/web_readonly.sql-editor.sql` | the Supabase or Neon **SQL editor** (no psql) | edit the `<CHANGE_ME>` placeholder before running               |

Both grant the same privileges. Re-running either is safe and sets a new password, which is also how
you rotate it. The password is never stored in the repo. The editor script refuses to run while the
placeholder is still there. Paste it, set the password, run it, then don't save the query, since
editors may keep it in their history.

### Neon (dev)

1. In the Neon console, open the project and use **Connect** to copy the connection string for the
   owner role (e.g. `neondb_owner`).
2. Run the script from the repo root:
   ```powershell
   psql "postgresql://neondb_owner:<owner password>@<endpoint>.neon.tech/neondb?sslmode=require" -f docs/sql/web_readonly.sql
   ```
   Or, without psql, paste `docs/sql/web_readonly.sql-editor.sql` into the Neon **SQL Editor**
   (it runs as the owner role).
3. Use the same host and database with the new role as `WEB_DATABASE_URL`:
   `postgresql://web_readonly:<web password>@<endpoint>.neon.tech/neondb?sslmode=require`

### Supabase (production)

1. In the Supabase dashboard, open **Connect** and copy the **Session pooler** string for the
   `postgres` user (username `postgres.<project-ref>`, port 5432).
2. Run the script from the repo root:
   ```powershell
   psql "postgresql://postgres.<project-ref>:<postgres password>@aws-0-<region>.pooler.supabase.com:5432/postgres" -f docs/sql/web_readonly.sql
   ```
   Or, without psql, paste `docs/sql/web_readonly.sql-editor.sql` into the Supabase **SQL Editor**
   (it runs as `postgres`).
3. The role is created as `web_readonly`, but on the Supabase pooler the **username is
   `web_readonly.<project-ref>`** (role name, a dot, then the project ref). Plain `web_readonly`
   is rejected there. The web app runs on serverless functions, so use the **transaction pooler**
   (port 6543, see [Database connections](#database-connections)):
   `postgresql://web_readonly.<project-ref>:<web password>@aws-0-<region>.pooler.supabase.com:6543/postgres`
   Set it as `WEB_DATABASE_URL` wherever the production web app runs. Do not put it in a local `.env`.

### Quick check

Connected as `web_readonly`, `SELECT count(*) FROM web_title_odds;` works and
`SELECT count(*) FROM predictions;` fails with `permission denied`.

## Database connections

`lib/db/index.ts` creates one postgres-js client per server instance with `prepare: false`,
`max: 3` in production (10 in development), `idle_timeout: 20` s and `connect_timeout: 10` s. Why:

- In production the app runs on serverless functions. Each warm instance keeps its own pool, so
  connections multiply with traffic; Supabase's **transaction pooler** (port 6543) multiplexes many
  short client connections onto a few database connections, which is what serverless needs. The
  session pooler (5432) pins a database connection per client connection and runs out quickly.
- The transaction pooler hands each transaction to whichever server connection is free, so
  prepared statements created on one are missing on the next: `prepare: false` sends every query
  unprepared.
- A small `max` still lets a page's sections query in parallel without one instance hogging the
  pooler, and `idle_timeout` releases connections from instances that have gone quiet.

## Live refresh

Data reads are cached with `"use cache"` and the tags in `lib/data/tags.ts` (`matches`, `odds`,
`scoreboard`, `backtest`). After each pipeline run that changed something (status `ok`), the
`matchday-pipeline` workflow calls:

```text
POST ${SITE_URL}/api/revalidate
Authorization: Bearer ${REVALIDATE_SECRET}
```

The route checks the token in constant time, returns 401 for anything else, and expires every tag
with `revalidateTag(tag, { expire: 0 })` (`updateTag` only works in Server Actions), so the next
visit to each page reads fresh data. The response is `{"revalidated": [...tags], "now": ...}`.

Setup: add `SITE_URL` (the deployed origin, no trailing slash) and `REVALIDATE_SECRET` as GitHub
Actions repository secrets, and the same `REVALIDATE_SECRET` in the web app's environment. Without
`SITE_URL` the workflow skips the call and says so in the job summary; a failed call is a warning,
never a failed job.

## Scripts

```powershell
pnpm dev:web                      # repo root
pnpm --filter web lint
pnpm --filter web typecheck
pnpm --filter web test            # Vitest
pnpm --filter web build
pnpm --filter web screenshots     # Playwright: needs the dev server on :3000; writes ./screenshots (gitignored)
                                  #   also reports horizontal overflow and tap targets under 24x24 on phones
pnpm --filter web screenshots:readme  # README images from the live site (BASE_URL to override) -> docs/screenshots
```

Team names and badge codes come from `lib/teams/display.ts`, keyed by football-data team id, with
the stored short name / TLA as fallback. Club colours stay in `lib/teams/colors.ts`, keyed by the
stored TLA. Model labels come from `lib/models/labels.ts`.
