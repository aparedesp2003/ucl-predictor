# apps/web

Next.js front end for the UCL predictor. It only **reads** the database, through three views that
`apps/engine` creates (migration `5c2e7a91d4b3_week5_web_views`):

| View                    | What it holds                                                     |
| ----------------------- | ----------------------------------------------------------------- |
| `web_match_predictions` | Every match from 2026-27 on, with the official primary prediction |
| `web_title_odds`        | Per team, the latest simulation of the current season             |
| `web_model_scoreboard`  | Live log loss / RPS per model and season, with `is_primary`       |

Drizzle definitions for them are hand-written in `lib/db/schema.ts` (`pgView(...).existing()`).
Never run `drizzle-kit push`, `migrate` or `generate`: the schema belongs to the engine (Alembic).

## Environment

Both variables live in the repo-root `.env` (see `.env.example`).

- `WEB_DATABASE_URL`: connection string for the `web_readonly` role. Required in production.
- `DATABASE_URL`: the engine's owner connection. In development only, the web falls back to it
  (with a console warning) when `WEB_DATABASE_URL` is empty.

`pnpm --filter web build` needs no database: every data section reads at request time.

## The `web_readonly` role

`docs/sql/web_readonly.sql` creates (or updates) a login role that can `SELECT` the three views
above and nothing else. It does not change any other role's privileges. Run it once per database
with `psql`, connected as the database owner. Re-running it is safe and sets a new password, which
is also how you rotate it.

The script asks for the password, which keeps it out of your shell history. You can also pass it
with `-v web_password=...`. The password is never stored in the repo.

### Neon (dev)

1. In the Neon console, open the project and use **Connect** to copy the connection string for the
   owner role (e.g. `neondb_owner`).
2. Run the script from the repo root:
   ```powershell
   psql "postgresql://neondb_owner:<owner password>@<endpoint>.neon.tech/neondb?sslmode=require" -f docs/sql/web_readonly.sql
   ```
3. Use the same host and database with the new role as `WEB_DATABASE_URL`:
   `postgresql://web_readonly:<web password>@<endpoint>.neon.tech/neondb?sslmode=require`

### Supabase (production)

1. In the Supabase dashboard, open **Connect** and copy the **Session pooler** string for the
   `postgres` user (username `postgres.<project-ref>`, port 5432).
2. Run the script from the repo root:
   ```powershell
   psql "postgresql://postgres.<project-ref>:<postgres password>@aws-0-<region>.pooler.supabase.com:5432/postgres" -f docs/sql/web_readonly.sql
   ```
3. On the pooler the new role connects as `web_readonly.<project-ref>`:
   `postgresql://web_readonly.<project-ref>:<web password>@aws-0-<region>.pooler.supabase.com:5432/postgres`
   Set it as `WEB_DATABASE_URL` wherever the production web app runs. Do not put it in a local `.env`.

### Quick check

Connected as `web_readonly`, `SELECT count(*) FROM web_title_odds;` works and
`SELECT count(*) FROM predictions;` fails with `permission denied`.

## Scripts

```powershell
pnpm dev:web                      # repo root
pnpm --filter web lint
pnpm --filter web typecheck
pnpm --filter web test            # Vitest
pnpm --filter web build
pnpm --filter web screenshots     # Playwright: needs the dev server on :3000; writes ./screenshots (gitignored)
```
