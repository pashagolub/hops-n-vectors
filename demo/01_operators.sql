-- ============================================================
-- GUD-003 | 01_operators.sql
-- DEMONSTRATES: pgvector distance operators
--   <->   Euclidean (L2) distance
--   <#>   Negative inner product (similarity flipped)
--   <=>   Cosine distance      ← our main operator
--   <+>   L1 / taxicab distance
-- EXPECTED OBSERVATIONS:
--   * Identical vectors  → cosine 0  (same direction)
--   * Orthogonal vectors → cosine 1  (maximally dissimilar)
--   * Opposite vectors   → cosine 2  (anti-parallel)
--   * Real beer query returns IPA neighbours for Centennial IPA
-- READ-ONLY — no DDL, no DML
-- ============================================================

\pset pager off

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '  01 · pgvector distance operators'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'

\echo ''
\echo '── [1] Four operators on the same pair of 3-D vectors ──'

SELECT
    operator,
    round(distance::numeric, 6) AS distance
FROM (
    VALUES
        ('L2      <->',  ('[1,2,3]'::vector(3) <->  '[4,5,6]'::vector(3))::float),
        ('cosine  <=>',  ('[1,2,3]'::vector(3) <=>  '[4,5,6]'::vector(3))::float),
        ('neg-IP  <#>',  ('[1,2,3]'::vector(3) <#>  '[4,5,6]'::vector(3))::float),
        ('L1      <+>',  ('[1,2,3]'::vector(3) <+>  '[4,5,6]'::vector(3))::float)
) t(operator, distance);

\echo ''
\echo '── [2] Cosine special cases ──'

SELECT
    label,
    round(dist::numeric, 4) AS cosine_dist
FROM (
    VALUES
        ('identical   [1,2,3] vs [1,2,3]',   ('[1,2,3]'::vector(3) <=> '[1,2,3]'::vector(3))::float),
        ('orthogonal  [1,0,0] vs [0,1,0]',   ('[1,0,0]'::vector(3) <=> '[0,1,0]'::vector(3))::float),
        ('opposite    [1,2,3] vs [-1,-2,-3]', ('[1,2,3]'::vector(3) <=> '[-1,-2,-3]'::vector(3))::float)
) t(label, dist);

\echo ''
\echo '── [3] Real query: 5 nearest beers to "Centennial IPA" (cosine) ──'

SELECT
    b.beer_name,
    b.style,
    b.abv,
    round((b.embedding <=> q.embedding)::numeric, 4) AS cosine_dist
FROM beers b
CROSS JOIN (SELECT embedding FROM beers WHERE beer_name = 'Centennial IPA') q
WHERE b.beer_name <> 'Centennial IPA'
ORDER BY b.embedding <=> q.embedding
LIMIT 5;
