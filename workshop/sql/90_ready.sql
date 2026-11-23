-- Provenance and the readiness marker checked by 00_check.sql.
INSERT INTO dataset_meta (key, value)
SELECT 'embedding_' || setting, value FROM embed_model_info()
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO dataset_meta (key, value) VALUES
    ('workshop_event',   'WAWTech 2026, Warsaw'),
    ('workshop_ready',   'true')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

\echo ''
\echo '  Hops''n''Vectors workshop image ready.'
\echo '  Connect with:  docker exec -it beer psql'
\echo ''
