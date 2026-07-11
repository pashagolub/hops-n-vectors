---
title: Architecture Specification — "Hops'n'Vectors" PostgreSQL + pgvector Beer Recommendation Showcase
version: 1.2
date_created: 2026-07-06
last_updated: 2026-07-11
owner: hops-n-vectors maintainers
tags: [architecture, app, infrastructure, design, postgres, pgvector, docker, demo, workshop]
---

# Introduction

This specification defines a self-contained, Docker-Compose-based showcase project that demonstrates semantic similarity search in PostgreSQL using the `pgvector` extension. The project builds a beer recommendation system inspired by the FOSDEM 2025 talk "From Queries to Pints: Building a Beer Recommendation System with pgvector" (Andrzej Nowicki). A single `docker compose up` must produce a fully working environment: a bundled beer dataset is loaded, text embeddings are generated with a locally-running sentence-transformer model, vector indexes are created, and an interactive Text User Interface (TUI) plus `psql` access are made available for exploration. The project is intended for live demonstrations at technical presentations and workshops.

## 1. Purpose & Scope

**Purpose**: Provide a reproducible, zero-configuration demonstration environment that showcases:

1. Storing and querying vector embeddings in PostgreSQL via `pgvector`.
2. Building embeddings locally with a small, freely available embedding model.
3. Comparing exact (sequential scan) vs. approximate (HNSW, IVFFlat) nearest-neighbour search, including `EXPLAIN ANALYZE` output.
4. pgvector distance operators, filtering behaviour with approximate indexes, and iterative scan.
5. Scheduled, incremental embedding rebuilds using `pg_timetable` (embeddings follow data changes made by users).

**Scope**: Covers the container topology, service contracts, database schema, data pipeline, TUI behaviour, scheduled jobs, and demo/workshop scenarios. Does not cover production deployment, authentication hardening, high availability, or LLM/RAG integration (RAG is mentioned only as an optional talking point).

**Intended audience**: Developers and AI agents implementing the project; presenters running the demo; workshop attendees exploring the system.

**Assumptions**:

- The host is a common developer laptop (8 GB+ RAM, x86_64 or arm64) with Docker Engine and Docker Compose v2 installed.
- Internet access is available on first start (for embedding model download only); subsequent starts must work offline using cached artifacts. The dataset is bundled in the repository — no runtime download is required.
- Users may have zero prior knowledge of pgvector.

## 2. Definitions

| Term | Definition |
|---|---|
| **pgvector** | PostgreSQL extension providing the `vector` data type, distance operators, and ANN index types (HNSW, IVFFlat). |
| **ANN** | Approximate Nearest Neighbour — search that trades exactness for speed via specialized indexes. |
| **HNSW** | Hierarchical Navigable Small World — graph-based ANN index type in pgvector. |
| **IVFFlat** | InVerted File Flat — clustering-based ANN index type in pgvector. |
| **Embedding** | Numerical vector representation of an object (here: beer description text) produced by an embedding model. |
| **Embedding model** | ML model mapping text to fixed-dimension vectors; here `sentence-transformers/all-MiniLM-L12-v2` (384 dimensions). |
| **Cosine distance** | Distance metric `1 - cosine similarity`; pgvector operator `<=>`. |
| **TUI** | Text User Interface — interactive terminal program for entering prompts and viewing recommendations. |
| **pg_timetable** | Advanced job scheduler for PostgreSQL (by CYBERTEC), running as a separate container, storing job definitions in the database. |
| **Sentence Transformers** | Python library (`sentence-transformers`) for computing text embeddings locally. |
| **Dataset** | "Beer Profile and Ratings Data Set" (Kaggle, ruthgn), CC BY 4.0, ~3,300 beers with names, styles, descriptions, and taste profiles. The dataset is static (last updated ~2021) and is bundled in the repository as a snapshot. |
| **RAG** | Retrieval Augmented Generation — LLM pattern using vector search to fetch relevant context (out of scope; talking point only). |

## 3. Requirements, Constraints & Guidelines

### Functional Requirements

- **REQ-001**: The entire system MUST start with a single command: `docker compose up`.
- **REQ-002**: The system MUST run PostgreSQL (version 18 or newer) with the `pgvector` extension (version 0.7.0 or newer, to include `<+>`, `<~>`, `<%>` operators and iterative scan support).
- **REQ-003**: On first start, a loader component MUST read the bundled beer dataset CSV, validate and transform it, and load it into the `beers` table.
- **REQ-004**: An embedder component MUST generate a 384-dimension embedding for every beer row using `sentence-transformers/all-MiniLM-L12-v2` and store it in the `embedding vector(384)` column.
- **REQ-005**: The embedding text MUST be composed from the beer's descriptive fields (name, style, description/notes, and key taste attributes) concatenated into a single text per beer (no chunking; each beer is one embedding).
- **REQ-006**: The system MUST create both an HNSW index and demonstrate an IVFFlat index on the embedding column using `vector_cosine_ops` (IVFFlat MAY be created on demand via a demo script rather than at startup).
- **REQ-007**: A TUI MUST be available that accepts a free-text prompt (e.g., "lemon"), embeds it, and returns the top-N most similar beers ordered by cosine distance (`<=>`), with N configurable (default 5).
- **REQ-008**: The TUI MUST also support a "more like this beer" mode: given a beer id or name, return similar beers excluding the input beer itself.
- **REQ-009**: Users MUST be able to open an interactive `psql` session against the database with a single documented command (e.g., `docker compose exec postgres psql -U beer -d beer`).
- **REQ-010**: `pg_timetable` MUST run in the `scheduler` container and MUST be configured with a `rebuild_embeddings` job that rebuilds embeddings for rows where the embedding is missing or the source text changed since last embedding (e.g., after a presenter edits a beer's `info` via psql during a workshop). The job MUST be a pg_timetable PROGRAM task invoking the embedder directly inside the scheduler container (no cross-container signaling).
- **REQ-011**: Startup progress (row loading, embedding progress, index creation) MUST be visible in `docker compose up` log output in a human-readable form (progress counters or percentage).
- **REQ-012**: The repository MUST include a set of ready-to-run demo SQL scripts showcasing: distance operators (`<->`, `<#>`, `<=>`, `<+>`), exact vs. HNSW vs. IVFFlat query plans via `EXPLAIN ANALYZE`, filtering pitfalls with ANN indexes (fewer rows than `LIMIT`), `hnsw.iterative_scan` / `ivfflat.iterative_scan` settings, and similarity limitations (e.g., "healthy" vs "unhealthy" adjacency).
- **REQ-013**: Change detection for embedding rebuilds MUST be implemented (e.g., a hash column of the source text, or `embedded_at` vs `updated_at` timestamps), so the rebuild job only re-embeds changed or new rows.
- **REQ-014**: A second start of `docker compose up` MUST NOT re-download the model if it is already cached in a Docker volume, and MUST NOT duplicate rows (idempotent loading via upsert on a natural or surrogate key).

### Security Requirements

- **SEC-001**: Database credentials MUST be defined in the compose file / `.env` for demo convenience but MUST NOT be reused from any real system; PostgreSQL MUST NOT be exposed on the host network beyond the mapped localhost port (default `5432` mapped to `127.0.0.1:5432`).
- **SEC-002**: The loader MUST validate the dataset file (format and expected columns) before loading; malformed files MUST abort the load with a clear error rather than partially loading.
- **SEC-003**: All SQL executed by the TUI and pipeline components MUST use parameterized queries (no string interpolation of user input into SQL).

### Performance Requirements

- **PER-001**: The embedding model plus runtime MUST fit within 2 GB of RAM for the scheduler container; the total compose stack MUST run within 4 GB of RAM.
- **PER-002**: Full initial embedding of the dataset (~3,300 rows) MUST complete within 5 minutes on a typical laptop CPU (no GPU required or assumed).
- **PER-003**: TUI query latency (embed prompt + vector search) SHOULD be under 2 seconds after model warm-up.

### Constraints

- **CON-001**: Embedding model is fixed to `sentence-transformers/all-MiniLM-L12-v2` (384 dimensions, ~130 MB, Apache 2.0 license). The dimension `384` is a schema constant; changing the model requires a schema migration and full re-embed.
- **CON-002**: Dataset is the Kaggle "Beer Profile and Ratings Data Set" (ruthgn), licensed CC BY 4.0. Attribution MUST be included in the README and in a `dataset_meta` table or comment.
- **CON-003**: The dataset CSV MUST be bundled in the repository as the primary and only data source (permitted by CC BY 4.0 with attribution). The Kaggle dataset is static (last updated ~2021), so no runtime download or periodic re-sync is implemented; this guarantees the demo never fails due to network/auth issues.
- **CON-004**: No GPU dependencies. All components MUST run on CPU only, on both x86_64 and arm64 (Apple Silicon) Docker hosts.
- **CON-005**: All embedding generation happens locally; no external embedding/LLM API calls are permitted.
- **CON-006**: Only official or well-known base images may be used (e.g., `pgvector/pgvector:pg18`, `python:3.12-slim`). The `scheduler` image is a local build on `python:3.12-slim` that copies the `pg_timetable` binary from the official `cybertecpostgresql/pg_timetable` image (multi-stage build).

### Guidelines

- **GUD-001**: Prefer Python (`psycopg` v3 + `pgvector-python` + `sentence-transformers`) for the loader, embedder, and TUI, mirroring the talk's examples. A thin shell wrapper MAY provide the TUI entry point.
- **GUD-002**: Keep every component small and readable — the code itself is presentation material. Favor clarity over cleverness; comment the "why" of pgvector-specific choices.
- **GUD-003**: SQL demo scripts should be numbered and self-describing (e.g., `01_operators.sql`, `02_explain_no_index.sql`, `03_hnsw.sql`, `04_ivfflat.sql`, `05_filtering_pitfalls.sql`, `06_iterative_scan.sql`, `07_similarity_limits.sql`).
- **GUD-004**: Include a `Makefile` or task runner with shortcuts: `make up`, `make tui`, `make psql`, `make demo`, `make reset`.
- **GUD-005**: Document a "presenter's script" in the README: the recommended order of demo steps for a live talk.

### Patterns

- **PAT-001**: Pipeline stages (loader, embedder) run to completion sequentially in the `scheduler` container entrypoint before `pg_timetable` starts: load → embed → exec pg_timetable. Each stage exits non-zero on failure (failing the container) and its progress is observable in `docker compose up` output.
- **PAT-002**: Embedding rebuild jobs are incremental and idempotent — driven by `WHERE embedding IS NULL OR text_hash <> stored_hash` predicates, safe to run repeatedly.
- **PAT-003**: The embedder batches updates (`executemany` / `COPY`) rather than row-by-row commits.

## 4. Interfaces & Data Contracts

### 4.1 Container Topology (docker-compose services)

The stack consists of exactly **two containers**:

| Service | Image (indicative) | Role | Depends on |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg18` | PostgreSQL + pgvector; schema bootstrap via `/docker-entrypoint-initdb.d` | — |
| `scheduler` | local build (`python:3.12-slim` + `pg_timetable` binary) | Entrypoint runs loader → embedder to completion, then execs `pg_timetable`; hosts the Python tools (loader/embedder/TUI) | `postgres` (healthy) |

The TUI is not a separate service: it runs on demand from the same image, e.g., `docker compose run --rm scheduler tui` (or `docker compose exec scheduler python -m hopsnvectors.tui`).

Named volumes: `pgdata` (database), `model-cache` (Hugging Face model cache, mounted into `scheduler`). The dataset CSV ships in the repository and is bind-mounted read-only into the `scheduler` container.

### 4.2 Database Schema (core contract)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE beers (
    id           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    beer_name    text NOT NULL,
    brewery      text,
    style        text,
    abv          numeric(5,2),
    min_ibu      integer,
    max_ibu      integer,
    -- taste profile attributes from the dataset (bitterness, sweetness, etc.)
    info         text,          -- composed descriptive text used for embedding
    text_hash    text,          -- sha256 of info; drives incremental re-embedding
    embedding    vector(384),
    embedded_at  timestamptz,
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (beer_name, brewery, style)    -- natural key for idempotent upsert
);

-- Created by embedder after initial embedding pass:
CREATE INDEX beers_embedding_hnsw ON beers
    USING hnsw (embedding vector_cosine_ops);

CREATE TABLE dataset_meta (
    key   text PRIMARY KEY,
    value text
);  -- stores source URL, license (CC BY 4.0), snapshot version, load timestamp, row count
```

### 4.3 Vector Search Query Contract (used by TUI)

```sql
-- Prompt search (parameter $1 = prompt embedding, $2 = limit):
SELECT beer_name, brewery, style, info,
       embedding <=> $1 AS distance
FROM beers
ORDER BY embedding <=> $1
LIMIT $2;

-- "More like this" (parameter $1 = source beer id, $2 = limit):
SELECT b.beer_name, b.style, b.info,
       b.embedding <=> s.embedding AS distance
FROM beers b, (SELECT embedding FROM beers WHERE id = $1) s
WHERE b.id <> $1
ORDER BY b.embedding <=> s.embedding
LIMIT $2;
```

### 4.4 pg_timetable Job Contract

| Job | Schedule (default) | Action |
|---|---|---|
| `rebuild_embeddings` | every 15 minutes (`*/15 * * * *`) | PROGRAM task executing the embedder (e.g., `python -m hopsnvectors.embedder --once`) inside the `scheduler` container for rows `WHERE embedding IS NULL OR embedded_at IS NULL OR text_hash IS DISTINCT FROM <hash of info>` |

The job is registered by an idempotent SQL script executed at bootstrap (`timetable.add_job` / chain definitions) with `kind => 'PROGRAM'`. Because pg_timetable and the embedder live in the same container, the PROGRAM task runs the embedder directly — no signaling, sidecars, or cross-container orchestration. The schedule MUST be overridable via an environment variable so presenters can trigger visible re-embedding during a workshop (e.g., set to every minute). Because the source dataset is a static snapshot, no dataset re-sync job exists; the rebuild job reacts to changes users make directly in the database.

### 4.5 TUI Command Contract

| Input | Behaviour |
|---|---|
| free text (e.g., `lemon`) | Embed prompt, show top-N beers with name, style, truncated info, and distance |
| `:like <id>` | "More like this" search for beer `<id>` |
| `:top <n>` | Set result count N (1–50) |
| `:explain` | Toggle: also print the `EXPLAIN ANALYZE` plan of the executed search query |
| `:help` | Show commands |
| `:quit` / Ctrl-D | Exit |

### 4.6 Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `beer` / `beer` / `beer` | Database credentials |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L12-v2` | Model id (informative; dimension is fixed at 384) |
| `EMBED_BATCH_SIZE` | `64` | Rows per embedding batch |
| `REBUILD_SCHEDULE` | see 4.4 | pg_timetable cron override for the re-embed job |
| `TOP_N_DEFAULT` | `5` | Default result count in TUI |

## 5. Acceptance Criteria

- **AC-001**: Given a clean checkout and a machine with Docker, When the user runs `docker compose up`, Then within 10 minutes the logs show row loading (~3,300 rows from the bundled dataset), embedding progress reaching 100%, HNSW index creation, and a message explaining how to start the TUI and psql.
- **AC-002**: Given the stack is up, When the user runs the documented TUI command and enters `lemon`, Then at least 5 beers are returned within 2 seconds, and citrus/lemon-themed beers rank at the top.
- **AC-003**: Given the stack is up, When the user opens `psql` and runs `SELECT count(*) FROM beers WHERE embedding IS NOT NULL;`, Then the count equals the total row count.
- **AC-004**: Given demo script `02_explain_no_index.sql` is run with the HNSW index dropped, When `EXPLAIN ANALYZE` output is inspected, Then it shows a sequential scan with top-N heapsort; and after re-creating the HNSW index (`03_hnsw.sql`), the plan shows an index scan on the HNSW index with lower execution time.
- **AC-005**: Given a beer row's `info` text is updated via psql, When the `rebuild_embeddings` pg_timetable job next runs, Then only that row's embedding is regenerated (verifiable via `embedded_at`).
- **AC-006**: Given the stack was fully started once, When the user runs `docker compose down` (without `-v`) followed by `docker compose up`, Then no model re-download occurs, no duplicate rows are created, and the system is ready in under 1 minute.
- **AC-007**: Given no network access and a warm model cache, When the stack starts, Then the loader completes from the bundled dataset and the system reaches ready state fully offline.
- **AC-008**: Given demo script `05_filtering_pitfalls.sql` is run, Then it demonstrably returns fewer rows than `LIMIT` under a selective `WHERE` filter with the ANN index, and returns the full expected count after enabling iterative scan.
- **AC-009**: The system shall run entirely on CPU and complete initial embedding of the full dataset in under 5 minutes on a 4-core laptop.
- **AC-010**: Given the stack is up, When the user runs `SELECT * FROM timetable.chain;` in psql, Then the scheduled `rebuild_embeddings` job is visible.

## 6. Test Automation Strategy

- **Test Levels**: Unit (Python components), Integration (against a real pgvector container), End-to-End (full compose stack).
- **Frameworks**: `pytest` with `testcontainers-python` (or compose-driven fixtures) for integration; `ruff` for linting; `shellcheck` for shell wrappers.
- **Unit scope**: dataset parsing/validation, text composition for embedding, hash-based change detection, TUI command parsing (embedding model mocked).
- **Integration scope**: schema bootstrap, upsert idempotency, vector search ordering with a fixed test model or precomputed vectors, pg_timetable job registration and incremental re-embed behaviour.
- **E2E scope**: a CI job runs `docker compose up`, waits for readiness, asserts AC-001/AC-002/AC-003 via scripted checks (non-interactive TUI invocation, e.g., `tui --query lemon --json`).
- **Test Data Management**: a miniature fixture CSV (~20 beers) committed to the repo; E2E may use the bundled full snapshot to avoid network dependency in CI.
- **CI/CD Integration**: GitHub Actions workflow with jobs: lint → unit → integration → e2e (e2e allowed to be a nightly/manual job due to runtime).
- **Coverage Requirements**: ≥80% line coverage on loader/embedder/TUI Python code.
- **Performance Testing**: E2E job records total startup time and embedding throughput; fails if initial embedding exceeds the PER-002 budget on the CI runner class.

## 7. Rationale & Context

- **Why beers**: matches the source talk; a fun, relatable domain that keeps workshop audiences engaged while showing real vector-search mechanics (e.g., prompt "lemon" surfacing citrus beers).
- **Why all-MiniLM-L12-v2**: small (~130 MB, 384 dims), Apache-2.0 licensed, runs comfortably on laptop CPUs, and is the exact model used in the source presentation — query plans and timings will resemble the slides.
- **Why one embedding per beer (no chunking)**: descriptions are short (<4,000 chars); chunking is deliberately out of scope but referenced in the README as the "real life" next step, mirroring slides 48–51.
- **Why both HNSW and IVFFlat**: the core teaching moment is comparing exact scan vs. two ANN index types with `EXPLAIN ANALYZE`, showing the accuracy/speed trade-off and index-specific behaviour.
- **Why pg_timetable**: demonstrates a realistic operational pattern — data changes over time and embeddings must be kept in sync — using a database-native scheduler that itself is demo-worthy in workshops; presenters edit a beer's description in psql and watch the scheduled PROGRAM task re-embed just that row.
- **Why a single scheduler container with bundled tools**: pg_timetable's PROGRAM task kind executes binaries on the host where the scheduler runs; bundling the Python tools in the same image lets the re-embed job invoke the embedder directly, avoiding cross-container signaling and shrinking the stack to two containers (postgres + scheduler). The entrypoint sequence (load → embed → exec pg_timetable) keeps the pipeline observable in `docker compose up` output (REQ-011) and each stage independently re-runnable.
- **Why bundled dataset (no runtime download)**: the Kaggle dataset is a static snapshot (last updated ~2021), so periodic re-sync would add failure modes (network, Kaggle auth — a classic live-demo killer) without ever fetching new data. CC BY 4.0 permits redistribution with attribution, making the demo fully network-independent for data.

## 8. Dependencies & External Integrations

### External Systems

- **EXT-001**: Hugging Face Hub (model hosting) — one-time HTTPS download of `all-MiniLM-L12-v2` on first start, cached in a Docker volume thereafter. The only runtime network dependency.

### Third-Party Services

- **SVC-001**: None at runtime after the initial model download. The system MUST be fully functional offline once the model cache is warm.

### Infrastructure Dependencies

- **INF-001**: Docker Engine ≥ 24 and Docker Compose v2 — the only host prerequisites.
- **INF-002**: Host resources — ≥4 GB RAM available to Docker, ≥5 GB disk (images + model + data), CPU-only.

### Data Dependencies

- **DAT-001**: Beer Profile and Ratings Data Set (Kaggle, ruthgn) — CSV, ~3,300 rows, CC BY 4.0; static snapshot (last updated ~2021) bundled in-repo and loaded at first start; no runtime access to Kaggle.

### Technology Platform Dependencies

- **PLT-001**: PostgreSQL ≥ 18 with pgvector ≥ 0.7.0 — required for the full operator set and iterative scan features showcased.
- **PLT-002**: pg_timetable (current stable) — scheduler; stores its schema (`timetable`) in the demo database.
- **PLT-003**: Python ≥ 3.11 with sentence-transformers, psycopg 3, and pgvector client library — loader, embedder, TUI runtime.

### Compliance Dependencies

- **COM-001**: CC BY 4.0 attribution for the dataset — attribution text in README and `dataset_meta` table.
- **COM-002**: Apache 2.0 license notice for the embedding model — noted in README.
- **COM-003**: Responsible-consumption disclaimer — README and TUI banner must state the project is for informational/entertainment purposes (mirroring the source talk's disclaimer).

## 9. Examples & Edge Cases

```text
# Happy path (presenter flow)
$ docker compose up
postgres   | database system is ready to accept connections
scheduler  | validating bundled dataset ... ok
scheduler  | loaded 3358 beers (inserted=3358 updated=0)
scheduler  | embedding 3358/3358 (100%) in 142s
scheduler  | CREATE INDEX beers_embedding_hnsw ... done
scheduler  | Run: docker compose run --rm scheduler tui   |   psql: docker compose exec postgres psql -U beer beer
scheduler  | starting pg_timetable ...

$ docker compose run --rm scheduler tui
🍺 > lemon
 1. Sun Drift        (Saison)  d=0.31  "…bright notes of citrus and black tea…"
 2. Lemon Lager      (Lager)   d=0.34  "…freshly squeezed lemon juice…"
 ...
🍺 > :like 2612
 ...
```

```sql
-- Edge case: ANN filtering returns fewer rows than LIMIT (05_filtering_pitfalls.sql)
SELECT beer_name FROM beers
WHERE style = 'Rare Style'          -- highly selective filter
ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 42)
LIMIT 5;                            -- may return < 5 rows with HNSW!

SET hnsw.iterative_scan = relaxed_order;  -- fix: keep scanning until enough rows
```

Edge cases the implementation MUST handle:

| # | Edge case | Required behaviour |
|---|---|---|
| 1 | Bundled CSV missing or corrupt (e.g., bad checkout, Git LFS pointer file) | Validation (SEC-002) fails fast with a clear message; no partial load |
| 2 | Duplicate rows in source CSV | Deduplicate on natural key during load; log count |
| 3 | Empty/NULL description fields | Compose `info` from available fields; skip embedding only if `info` is empty, log skipped ids |
| 4 | TUI prompt is empty or > 4,000 chars | Reject with a friendly message; never send to model/DB |
| 5 | `:like <id>` with nonexistent id | Friendly "beer not found" message |
| 6 | Embedder interrupted mid-run (Ctrl-C, crash) | Rerun continues from pending rows (PAT-002); no partial-batch corruption |
| 7 | pg_timetable PROGRAM task fires while another embed run is in progress (e.g., manual `docker compose run` or overlapping schedules) | Job's WHERE predicate makes concurrent runs harmless; advisory lock or `FOR UPDATE SKIP LOCKED` recommended |
| 8 | Non-ASCII beer names/descriptions | UTF-8 end-to-end; database `UTF8` encoding mandatory |
| 9 | arm64 host (Apple Silicon) | All images multi-arch; no x86-only wheels |
| 10 | Hugging Face unreachable on first start (cold model cache) | Fail with a clear message explaining the one-time network requirement; retry-friendly |

## 10. Validation Criteria

- `docker compose config` validates; `docker compose up` on a clean machine satisfies AC-001 through AC-010.
- All demo SQL scripts in `demo/` run without error against the freshly started stack, in numbered order.
- `SELECT count(*) FROM beers WHERE embedding IS NULL AND info IS NOT NULL AND info <> '';` returns 0 after startup.
- The `rebuild_embeddings` pg_timetable chain exists and executes successfully at least once (check `timetable.execution_log`).
- The TUI non-interactive mode (`--query <text> --json`) returns valid JSON with N results — used by CI.
- Offline restart test: with networking disabled and warm volumes, the full stack reaches ready state.
- Linting (ruff, shellcheck, hadolint for Dockerfiles) passes; unit + integration test suites pass with ≥80% coverage on Python components.
- README contains: quickstart, presenter's script, dataset attribution (CC BY 4.0), model license note, and the responsible-consumption disclaimer.

## 11. Related Specifications / Further Reading

- Source talk: "From Queries to Pints — Building a Beer Recommendation System with pgvector", Andrzej Nowicki, FOSDEM 2025 (slides: `2025_PGVE_x86FgXC.pdf` in this repository)
- [pgvector — GitHub](https://github.com/pgvector/pgvector)
- [pgvector filtering & iterative scan documentation](https://github.com/pgvector/pgvector?tab=readme-ov-file#filtering)
- [sentence-transformers/all-MiniLM-L12-v2 — Hugging Face](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2)
- [Beer Profile and Ratings Data Set — Kaggle (CC BY 4.0)](https://www.kaggle.com/datasets/ruthgn/beer-profile-and-ratings-data-set)
- [pg_timetable — CYBERTEC PostgreSQL scheduler](https://github.com/cybertec-postgresql/pg_timetable)
- [Write You a Vector DB (IVFFlat & HNSW internals) — Alex Chi Z.](https://skyzh.github.io/write-you-a-vector-db/)
- [psycopg 3 documentation](https://www.psycopg.org/psycopg3/)
