-- Phase 2 bootstrap placeholder for the pg_timetable registration path.
--
-- This file intentionally stays side-effect free during PostgreSQL init because
-- docker-entrypoint SQL runs before the dedicated pg_timetable service connects
-- and creates its scheduler schema. Phase 5 replaces this placeholder with an
-- idempotent registration script that adds the rebuild_embeddings job using the
-- schedule from REBUILD_SCHEDULE.

DO $$
BEGIN
	RAISE NOTICE 'pg_timetable job registration is deferred until Phase 5 finalizes scheduler bootstrap.';
END
$$;
