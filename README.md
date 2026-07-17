# Hops'n'Vectors

A self-contained showcase of semantic similarity search in PostgreSQL using the
[pgvector](https://github.com/pgvector/pgvector) extension, built around a real
beer dataset. One command starts everything; no cloud APIs, no GPU, no Kaggle
account. Inspired by the FOSDEM 2025 talk
["From Queries to Pints: Building a Beer Recommendation System with pgvector"
by Andrzej Nowicki](https://archive.fosdem.org/2025/schedule/event/fosdem-2025-5531-from-queries-to-pints-building-a-beer-recommendation-system-with-pgvector/).

---

## Table of Contents

1. [Quickstart](#1-quickstart)
2. [Usage](#2-usage)
   - [TUI — interactive recommendations](#21-tui--interactive-recommendations)
   - [psql access](#22-psql-access)
3. [Presenter's script](#3-presenters-script)
4. [Architecture](#4-architecture)
5. [Configuration](#5-configuration)
6. [Demo scripts](#6-demo-scripts)
7. [Dataset](#7-dataset)
8. [Embedding model](#8-embedding-model)
9. [Real-life next steps](#9-real-life-next-steps)
10. [Responsible-consumption disclaimer](#10-responsible-consumption-disclaimer)

---

## 1. Quickstart

**Prerequisites:** Docker Engine ≥ 24 and Docker Compose v2. No other tools needed.

```bash
git clone https://github.com/pashagolub/hops-n-vectors.git
cd hops-n-vectors
docker compose up          # or: make up
```

**What to expect in the logs:**

```
postgres   | database system is ready to accept connections
scheduler  | validating bundled dataset ... ok
scheduler  | loaded 3197 beers (inserted=3197 updated=0)
scheduler  | embedding 3197/3197 (100%) in ~2 min
scheduler  | CREATE INDEX beers_embedding_hnsw ... done
scheduler  | Run: docker compose run --rm scheduler tui
scheduler  |      psql: docker compose exec postgres psql -U beer -d beer
scheduler  | starting pg_timetable ...
```

**First start:** the embedding model (`all-MiniLM-L12-v2`, ~130 MB) is
downloaded once from Hugging Face and stored in the `model-cache` Docker volume.
This is the **only** network dependency — the beer dataset is bundled in the
repository.

**Subsequent starts:** the model is loaded from the volume; no network access is
required at all. `docker compose down` (without `-v`) preserves both volumes;
a second `up` is ready in under a minute with no duplicate rows and no
re-download.

---

## 2. Usage

### 2.1 TUI — interactive recommendations

```bash
docker compose run --rm scheduler tui   # or: make tui
```

At the `🍺 >` prompt:

| Command | Behaviour |
|---|---|
| `lemon` (any free text) | Embed the prompt; show top-N similar beers (name, style, distance, excerpt) |
| `:like <id>` | "More like this" — beers similar to beer `<id>` |
| `:top <n>` | Set result count N (1–50); default is `TOP_N_DEFAULT` (5) |
| `:explain` | Toggle: also print `EXPLAIN ANALYZE` for the executed query |
| `:help` | Show all commands |
| `:quit` / Ctrl-D | Exit |

**Non-interactive / JSON mode** (useful for CI or scripting):

```bash
docker compose run --rm scheduler tui --query lemon --json
docker compose run --rm scheduler tui --query lemon --json --top 10
```

Returns a JSON array of result objects; exits after printing.

### 2.2 psql access

```bash
docker compose exec postgres psql -U beer -d beer   # or: make psql
```

Credentials: user `beer`, password `beer`, database `beer` (demo-only — see
[Configuration](#5-configuration)).

---

## 3. Presenter's script

Recommended live-demo order for a 20–30 minute talk or workshop.

### Step 1 — Walk through the startup logs

Run `docker compose up` in a visible terminal. Call out the three pipeline stages
printed to the log: **validate → load → embed → create HNSW index → hand off to
pg_timetable**. Point out the ~130 MB first-time model download and explain it
never happens again.

### Step 2 — TUI: search, like, explain

```bash
docker compose run --rm scheduler tui
```

- Type `lemon` — show that citrus/lemon-style beers rise to the top; distance
  values are cosine distance (0 = identical direction, 1 = orthogonal).
- Pick a result id with `:like <id>` — "more beers like this one".
- Toggle `:explain` — show the HNSW index scan in `EXPLAIN ANALYZE` output; note
  far fewer buffer reads than a sequential scan.

### Step 3 — Demo scripts in psql (run in numbered order)

```bash
docker compose exec postgres psql -U beer -d beer   # or: make psql
```

Then `\i /demo/NN_name.sql`, or run all at once with `make demo`.

| Script | What to say |
|---|---|
| `01_operators.sql` | "pgvector gives us four distance operators; `<=>` cosine is our workhorse — watch identical vectors return 0 and orthogonal vectors return 1." |
| `02_explain_no_index.sql` | "Without an index PostgreSQL reads every row — sequential scan, top-N heapsort. Notice the execution time. (Index is dropped by this script.)" |
| `03_hnsw.sql` | "HNSW graph-based ANN: the plan now shows an index scan, execution time drops dramatically, recall stays high." |
| `04_ivfflat.sql` | "IVFFlat partitions the space into clusters. `probes` trades speed for recall — great for showing the accuracy/speed knob." |
| `05_filtering_pitfalls.sql` | "ANN indexes apply your `WHERE` *after* fetching a fixed candidate set. A selective filter can silently return fewer rows than `LIMIT` — here's the proof." |
| `06_iterative_scan.sql` | "pgvector ≥ 0.8 adds iterative scan: `SET hnsw.iterative_scan = relaxed_order` keeps scanning until `LIMIT` is satisfied." |
| `07_similarity_limits.sql` | "Embeddings capture *topical* similarity, not logical polarity. A non-alcoholic beer neighbours a 10% ABV red ale — same style vocabulary, opposite ABV. Know your model's limits." |

### Step 4 — The pg_timetable moment (AC-005)

Show that embeddings stay in sync with data changes automatically.

**1. Edit a beer's description:**

```sql
-- In psql — note embedded_at before the change
SELECT id, beer_name, embedded_at FROM beers WHERE id = 1;

UPDATE beers SET info = info || ' extra hoppy' WHERE id = 1;
```

**2a. Wait for the scheduled job** (fires every 15 minutes by default).
Watch `docker compose up` output for `scheduler | rebuild_embeddings`.

**2b. Or trigger immediately:**

```sql
SELECT timetable.notify_chain_start(chain_id, 'hops-n-vectors-scheduler')
FROM timetable.chain
WHERE chain_name = 'rebuild_embeddings';
```

**3. Confirm only that row was re-embedded:**

```sql
-- Only beer id=1 has a fresh embedded_at; others are unchanged
SELECT id, beer_name, embedded_at
FROM beers
ORDER BY embedded_at DESC
LIMIT 5;
```

This illustrates incremental, hash-driven change detection: the rebuilder uses
`WHERE text_hash IS DISTINCT FROM sha256(info)`, so only truly changed rows are
re-processed.

> **Tip:** Set `REBUILD_SCHEDULE=* * * * *` in `.env` before starting to make
> the rebuild fire every minute — visible in real time during the demo.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ docker compose stack                                        │
│                                                             │
│  ┌──────────────────────┐     ┌──────────────────────────┐  │
│  │  postgres            │     │  scheduler               │  │
│  │  pgvector/pgvector   │◄────│  python:3.12-slim        │  │
│  │  :pg18               │     │  + pg_timetable binary   │  │
│  │                      │     │                          │  │
│  │  • pgvector ext      │     │  Entrypoint (once):      │  │
│  │  • beers table       │     │    1. loader             │  │
│  │  • HNSW index        │     │    2. embedder           │  │
│  │  • timetable schema  │     │    3. exec pg_timetable  │  │
│  └──────────────────────┘     │                          │  │
│                               │  TUI (on demand):        │  │
│  volumes:                     │    docker compose run    │  │
│  • pgdata                     │    --rm scheduler tui    │  │
│  • model-cache ─────────────► │                          │  │
│    (HF model, cached)         │  PROGRAM task:           │  │
│                               │    rebuild_embeddings    │  │
│  data/ (bind-mount, ro):      │    (*/15 * * * *)        │  │
│  • beer_data.csv              │    invokes embedder      │  │
│                               │    directly in container │  │
│                               └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Key design choices:**

- **Single scheduler container** — `pg_timetable`'s `PROGRAM` task kind executes
  binaries on the same host where the scheduler runs. Bundling the Python tools
  (loader, embedder, TUI) in the same image lets the re-embed job invoke the
  embedder directly — no cross-container signaling, no sidecars.
- **Entrypoint pipeline** — loader → embedder runs to completion before
  `pg_timetable` starts, making each stage observable in `docker compose up`
  output and independently re-runnable.
- **Bundled dataset** — the Kaggle CSV is committed to the repo (CC BY 4.0
  permits redistribution with attribution). No runtime download, no Kaggle auth:
  a classic live-demo failure mode eliminated.
- **One embedding per beer** — descriptions are short (<4,000 chars); no
  chunking needed. The schema constant is `vector(384)` matching
  `all-MiniLM-L12-v2`. Changing the model requires a schema migration and full
  re-embed.

---

## 5. Configuration

All variables live in `.env` (committed with demo-safe defaults).

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER` | `beer` | Database user (demo-only, do not reuse) |
| `POSTGRES_PASSWORD` | `beer` | Database password (demo-only) |
| `POSTGRES_DB` | `beer` | Database name |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L12-v2` | Model id (informational; schema dimension is fixed at 384) |
| `EMBED_BATCH_SIZE` | `64` | Rows per embedding batch |
| `REBUILD_SCHEDULE` | `*/15 * * * *` | pg_timetable cron for incremental re-embed job |
| `TOP_N_DEFAULT` | `5` | Default result count in TUI |

PostgreSQL is exposed only on `127.0.0.1:5432` — not on all interfaces.

---

## 6. Demo scripts

Scripts in `demo/` are numbered and self-describing. Run them in order inside
`psql`, or execute all at once:

```bash
make demo          # runs 01 through 07 in sequence
```

Individual execution (the `demo/` folder is mounted read-only at `/demo`
inside the postgres container):

```sql
\i /demo/01_operators.sql
```

See [Presenter's script §3](#step-3--demo-scripts-in-psql-run-in-numbered-order)
for a one-line "what to say" per script.

**Other Makefile targets:**

| Target | Action |
|---|---|
| `make up` | `docker compose up` |
| `make tui` | Open interactive TUI |
| `make psql` | Open psql session |
| `make demo` | Run all demo scripts in numbered order |
| `make reset` | Tear down stack and volumes (full reset) |
| `make test` | Run test suite |
| `make lint` | Run linter (ruff) |

---

## 7. Dataset

**Beer Profile and Ratings Data Set**
Author: ruthgn | License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
Source: <https://www.kaggle.com/datasets/ruthgn/beer-profile-and-ratings-data-set>

The CSV is bundled in this repository as `data/beer_profile_and_ratings.csv`
(snapshot date: 2026-07-06, ~3,197 beers). The dataset is static (last updated
~2021 on Kaggle); no runtime download or re-sync is performed. Attribution is
also stored in the `dataset_meta` table at runtime.

---

## 8. Embedding model

**`sentence-transformers/all-MiniLM-L12-v2`**
License: [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
Source: <https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2>

384-dimensional dense vectors, ~130 MB download, CPU-only inference. This is the
same model used in the source FOSDEM 2025 talk, so query plans and timings will
resemble the slides.

---

## 9. Real-life next steps

This project deliberately keeps each beer as **a single embedding**. In
production systems with longer documents the natural extension is **chunking**:
split each document into overlapping passages, embed each chunk separately, and
aggregate or re-rank at query time. Retrieval Augmented Generation (RAG)
combines this chunked index with an LLM to answer questions grounded in your
corpus. See slides 48–51 of the included PDF for a brief treatment.

---

## 10. Responsible-consumption disclaimer

This project is for **informational and entertainment purposes only**. Beer
recommendations are generated by a machine-learning model and carry no
endorsement of any product, brewery, or consumption level. Please drink
responsibly and in accordance with the laws of your jurisdiction.

---

*Inspired by "From Queries to Pints — Building a Beer Recommendation System with
pgvector", Andrzej Nowicki, FOSDEM 2025.*
