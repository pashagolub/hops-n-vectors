-- Idempotent registration of the rebuild_embeddings pg_timetable chain.
--
-- Execution contexts
-- ==================
-- 1. PostgreSQL initialisation (/docker-entrypoint-initdb.d/):
--    The timetable schema does not yet exist at this stage.  The DO block
--    detects this and exits gracefully with a NOTICE.
--
-- 2. pg_timetable scheduler startup (--file flag, see app/entrypoint.sh):
--    At this stage the timetable schema has been created by the scheduler
--    service.  The idempotency guard makes repeated invocations safe.
--
-- Job design (spec v1.2 §4.4, REQ-010)
-- ------------------------------------
-- Chain name : rebuild_embeddings
-- Schedule   : controlled by REBUILD_SCHEDULE in .env (default: */15 * * * *).
--              The scheduler entrypoint substitutes the value at startup; the
--              hardcoded default below applies only when this file is run
--              directly via psql outside of Compose.
-- Task kind  : PROGRAM
-- Command    : python -m hopsnvectors.embedder --once
--
-- pg_timetable and the Python tools live in the same scheduler container, so
-- the PROGRAM task executes the embedder directly -- no signaling, sidecars,
-- or cross-container orchestration.  embed_pending() re-embeds only rows
-- whose text_hash has drifted from the current info content, satisfying
-- AC-005.  FOR UPDATE SKIP LOCKED keeps concurrent invocations safe.

DO $do$
BEGIN
    -- PG-init guard: timetable schema not present yet -- skip silently.
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'timetable'
    ) THEN
        RAISE NOTICE 'timetable schema absent (PostgreSQL init phase) -- '
                     'rebuild_embeddings registration deferred to scheduler startup.';
        RETURN;
    END IF;

    -- Idempotency guard: skip if already registered.
    IF EXISTS (
        SELECT 1 FROM timetable.chain WHERE chain_name = 'rebuild_embeddings'
    ) THEN
        RAISE NOTICE 'rebuild_embeddings chain already registered -- skipping.';
        RETURN;
    END IF;

    -- Register the chain as a PROGRAM task executed inside the scheduler
    -- container.  The schedule supplied here is the hardcoded default; the
    -- docker-compose scheduler service overrides it at startup by
    -- substituting REBUILD_SCHEDULE from .env.
    PERFORM timetable.add_job(
        job_name       => 'rebuild_embeddings',
        job_schedule   => '*/15 * * * *',
        job_kind       => 'PROGRAM',
        job_command    => 'python',
        job_parameters => '["-m", "hopsnvectors.embedder", "--once"]'::jsonb
    );

    RAISE NOTICE 'rebuild_embeddings chain registered (PROGRAM task, schedule: */15 * * * *).';
END
$do$;
