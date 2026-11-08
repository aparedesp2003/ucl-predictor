-- Read-only login role for apps/web: version for the Supabase / Neon SQL editors (no psql).
-- Same effect as docs/sql/web_readonly.sql: creates or updates the web_readonly role and grants
-- it CONNECT on the current database, USAGE on schema public, and SELECT on the web_* views.
-- It changes no other role's privileges.
--
-- 1. Set web_password in the DECLARE below to a strong password (16+ characters).
--    Do not commit it.
-- 2. Run the whole script as the database owner (Supabase: postgres; Neon: the project owner).
-- 3. The editor may keep the query in its history: clear it, or rotate the password later with psql.
-- Re-running is safe and sets the new password, so it is also how to rotate it.

DO $$
DECLARE
  web_password text := '<CHANGE_ME>';
BEGIN
  -- The placeholder text appears only on the line above, so a find-and-replace cannot reach this check.
  IF web_password LIKE '<%>' OR length(web_password) < 16 THEN
    RAISE EXCEPTION 'Set web_password above to a strong password (16+ characters) first';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_readonly') THEN
    CREATE ROLE web_readonly LOGIN;
  END IF;
  EXECUTE format('ALTER ROLE web_readonly WITH LOGIN PASSWORD %L', web_password);

  EXECUTE format('GRANT CONNECT ON DATABASE %I TO web_readonly', current_database());
  GRANT USAGE ON SCHEMA public TO web_readonly;
  GRANT SELECT ON web_match_predictions, web_title_odds, web_model_scoreboard TO web_readonly;
END
$$;
