-- ============================================================
-- GUD-003 | 07_similarity_limits.sql
-- DEMONSTRATES: Semantic similarity pitfalls — embeddings capture
--   topical relatedness, NOT logical polarity
-- EXPECTED OBSERVATIONS:
--   * Non-alcoholic IPA (0.5% ABV) is surprisingly close to an 18%
--     imperial IPA — opposite alcohol content, same hop vocabulary
--   * Bud Light and an 18% imperial stout are still in the same
--     neighbourhood; IPA vs IPA is the closest pair for reference
--   * Neighbours of a non-alcoholic IPA are regular full-strength IPAs
-- WHY:
--   all-MiniLM-L12-v2 encodes semantic proximity; "non-alcoholic IPA"
--   and "imperial IPA" share far more vocabulary (hops, citrus, malt,
--   tasting notes) than they differ.  The model has no notion of
--   negation or polarity across beer attributes.
-- READ-ONLY — no DDL, no DML
-- ============================================================

\pset pager off

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '  07 · Semantic similarity pitfalls'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'

\echo ''
\echo '── [1] Pairwise cosine distances: "opposite" beers ──'
\echo '   Low cosine = MORE similar.  Note how "opposite" pairs'
\echo '   (non-alcoholic vs 18% imperial, light vs dark) are'
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
    -- 0.5 % ABV non-alcoholic IPA  vs  18 % ABV imperial IPA
    SELECT
        'non-alcoholic IPA  vs  18% imperial IPA' AS label,
        a.beer_name AS beer_a, a.abv AS abv_a,
        b.beer_name AS beer_b, b.abv AS abv_b,
        round((a.embedding <=> b.embedding)::numeric, 4) AS cosine_dist
    FROM beers a, beers b
    WHERE a.id = 5266   -- BrewDog Punk AF (0.5% non-alcoholic)
      AND b.id = 513    -- Dogfish Head 120 Minute IPA (18%)

    UNION ALL

    -- Light lager  vs  imperial stout
    SELECT
        'light lager        vs  imperial stout',
        a.beer_name, a.abv,
        b.beer_name, b.abv,
        round((a.embedding <=> b.embedding)::numeric, 4)
    FROM beers a, beers b
    WHERE a.id = 1573   -- Bud Light (4.2%)
      AND b.id = 536    -- Dogfish Head World Wide Stout (18%)

    UNION ALL

    -- Same-style reference: two IPAs from the same brewery (closest)
    SELECT
        'same style ref: IPA  vs  IPA',
        a.beer_name, a.abv,
        b.beer_name, b.abv,
        round((a.embedding <=> b.embedding)::numeric, 4)
    FROM beers a, beers b
    WHERE a.id = 512    -- Dogfish Head 60 Minute IPA
      AND b.id = 510    -- Dogfish Head 90 Minute IPA
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
CROSS JOIN (SELECT embedding FROM beers WHERE id = 1573) q   -- Bud Light
WHERE b.id <> 1573
ORDER BY b.embedding <=> q.embedding
LIMIT 8;

\echo ''
\echo '── [3] Nearest neighbours of a non-alcoholic IPA ──'
\echo '   Expect full-strength IPAs to appear; the model ignores polarity.'
\echo ''

SELECT
    b.beer_name,
    b.style,
    b.abv,
    round((b.embedding <=> q.embedding)::numeric, 4) AS cosine_dist
FROM beers b
CROSS JOIN (SELECT embedding FROM beers WHERE id = 5266) q   -- BrewDog Punk AF
WHERE b.id <> 5266
ORDER BY b.embedding <=> q.embedding
LIMIT 8;

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '  KEY INSIGHT'
\echo '  Embeddings compress meaning into cosine distance.'
\echo '  "Non-alcoholic IPA" and "18% imperial IPA" share the'
\echo '  same beer vocabulary → they cluster together.  If you'
\echo '  need to filter on ABV, style, or other attributes,'
\echo '  combine WHERE clauses with the ORDER BY <=> — do not'
\echo '  rely on vector similarity alone for structured data.'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
