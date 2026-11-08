-- Read-only login role for apps/web. Run once per database (Neon dev, Supabase prod) as the owner
-- role, with psql. It only creates/alters the web_readonly role and grants it:
--   CONNECT on the current database, USAGE on schema public, and SELECT on the web_* views.
-- It changes no other role's privileges. The views run with their owner's rights, so the role
-- needs no grant on the underlying tables (and cannot read them).
--
-- Usage (the password never goes into the repo):
--   psql "<owner connection string>" -f docs/sql/web_readonly.sql
--     -> prompts for the password (kept out of shell history), or pass -v web_password=...
-- Re-running is safe and resets the password, so it is also how to rotate it.
-- See apps/web/README.md for the Neon and Supabase specifics.

\set ON_ERROR_STOP on

\if :{?web_password}
\else
  \prompt 'Password for web_readonly: ' web_password
\endif

SELECT 'CREATE ROLE web_readonly LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_readonly')
\gexec

ALTER ROLE web_readonly WITH LOGIN PASSWORD :'web_password';

SELECT format('GRANT CONNECT ON DATABASE %I TO web_readonly', current_database())
\gexec

GRANT USAGE ON SCHEMA public TO web_readonly;

GRANT SELECT ON web_match_predictions, web_title_odds, web_model_scoreboard TO web_readonly;
