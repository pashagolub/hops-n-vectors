-- Asynchronous freshness: re-embed stale rows once a minute.
--
-- This is the "batch" half of the story told in exercise 05.  The synchronous
-- half is a trigger on beers, which attendees write themselves.
CREATE EXTENSION IF NOT EXISTS pg_cron;

SELECT cron.schedule('refresh-embeddings', '* * * * *', 'SELECT refresh_embeddings()')
WHERE NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'refresh-embeddings');
