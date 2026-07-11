-- ============================================================
-- GUD-003 | 07_similarity_limits.sql
-- DEMONSTRATES: Semantic similarity pitfalls — embeddings capture
--   topical relatedness, NOT logical polarity
-- EXPECTED OBSERVATIONS:
--   * Non-alcoholic beer (0.5% ABV) cosine ≈ 0.58 from a 19.6% stout
--     — closer than you'd expect given the opposite alcohol content
--   * A light lager and a dark dubbel cosine ≈ 0.68 — still in the
--     same neighbourhood; IPA vs IPA is 0.41 for reference
--   * Neighbours of a non-alcoholic beer include 10% ABV red ales
--   * Neighbours of Bud Light include dark wheat beers
-- WHY:
--   all-MiniLM-L12-v2 encodes semantic proximity; "non-alcoholic beer"
--   and "imperial stout" share far more vocabulary (hops, malt, ABV,
--   tasting notes, brewery) than they differ.  The model has no notion
--   of negation or polarity across beer attributes.
-- READ-ONLY — no DDL, no DML
-- ============================================================

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '  07 · Semantic similarity pitfalls'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'

\echo ''
\echo '── [1] Pairwise cosine distances: "opposite" beers ──'
\echo '   Low cosine = MORE similar.  Note how "opposite" pairs'
\echo '   (non-alcoholic vs imperial stout, light vs dark) are'
\echo '   still closer than you might expect — all are beer texts.'
\echo ''

SELECT
    label,
    beer_a,
    abv_a,
    beer_b,
    abv_b,
    cosine_dist
FROM (
    -- 0.50 % ABV non-alcoholic  vs  19.6 % ABV imperial stout
    SELECT
        'non-alcoholic  vs  imperial stout' AS label,
        a.beer_name AS beer_a, a.abv AS abv_a,
        b.beer_name AS beer_b, b.abv AS abv_b,
        round((a.embedding <=> b.embedding)::numeric, 4) AS cosine_dist
    FROM beers a, beers b
    WHERE a.id = 1689   -- Buckler Non-Alcoholic Brew
      AND b.id = 2514   -- Chocolate Rain  (19.6 % ABV stout)

    UNION ALL

    -- Light lager  vs  dark dubbel
    SELECT
        'light lager    vs  dark dubbel',
        a.beer_name, a.abv,
        b.beer_name, b.abv,
        round((a.embedding <=> b.embedding)::numeric, 4)
    FROM beers a, beers b
    WHERE a.id = 1344   -- Bud Light
      AND b.id = 619    -- Dark Abby (Dubbel)

    UNION ALL

    -- Same-style reference: two American IPAs (should be closest)
    SELECT
        'same style ref: IPA  vs  IPA',
        a.beer_name, a.abv,
        b.beer_name, b.abv,
        round((a.embedding <=> b.embedding)::numeric, 4)
    FROM beers a, beers b
    WHERE a.id = 802    -- 60 Minute IPA
      AND b.id = 807    -- Centennial IPA
) t
ORDER BY cosine_dist;

\echo ''
\echo '── [2] Nearest neighbours of "Bud Light" (light lager, 4.2 % ABV) ──'
\echo '   Watch for dark / heavy styles appearing in the results.'
\echo ''

SELECT
    b.beer_name,
    b.style,
    b.abv,
    round((b.embedding <=> q.embedding)::numeric, 4) AS cosine_dist
FROM beers b
CROSS JOIN (SELECT embedding FROM beers WHERE id = 1344) q   -- Bud Light
WHERE b.id <> 1344
ORDER BY b.embedding <=> q.embedding
LIMIT 8;

\echo ''
\echo '── [3] Nearest neighbours of a non-alcoholic beer ──'
\echo '   Expect high-ABV beers to appear; the model ignores polarity.'
\echo ''

SELECT
    b.beer_name,
    b.style,
    b.abv,
    round((b.embedding <=> q.embedding)::numeric, 4) AS cosine_dist
FROM beers b
CROSS JOIN (SELECT embedding FROM beers WHERE id = 1689) q   -- Buckler Non-Alcoholic
WHERE b.id <> 1689
ORDER BY b.embedding <=> q.embedding
LIMIT 8;

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '  KEY INSIGHT'
\echo '  Embeddings compress meaning into cosine distance.'
\echo '  "Non-alcoholic" and "19% stout" share the same beer'
\echo '  vocabulary → they cluster together.  If you need to'
\echo '  filter on ABV, style, or other attributes, combine'
\echo '  WHERE clauses with the ORDER BY <=> — do not rely on'
\echo '  vector similarity alone to encode structured properties.'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
