# Hops'n'Vectors - Workshop

Semantic beer search, running entirely inside PostgreSQL. No cloud, no API key,
no GPU, and after the first pull, no network.

You will need **Docker Desktop running** and about **1.5 GB of free disk**. No
Docker, or bad Wi-Fi? A free browser-based cloud shell works just as well - see
[Running it in a browser instead](#running-it-in-a-browser-instead).

## Before the workshop (do this on good Wi-Fi)

```bash
docker pull ghcr.io/pashagolub/hops-n-vectors:pg18
```

Roughly 280 MB. Conference Wi-Fi is not the place to discover you skipped this.

## Start

```bash
docker run -d --name beer -p 5432:5432 ghcr.io/pashagolub/hops-n-vectors:pg18
```

Wait until `docker ps` shows `(healthy)` - normally about 15 seconds. Then:

```bash
docker exec -it beer psql
```

That is the whole setup. You do not need a psql client of your own.

```sql
\i /workshop/00_check.sql
```

Everything should say `OK`.

## What is inside

| | |
|---|---|
| PostgreSQL 18 | with `pg_cron` and `plpython3u` |
| pgvector 0.8.6 | the `vector` type, `<=>`, HNSW and IVFFlat |
| all-MiniLM-L12-v2 | a 34 MB quantized ONNX model, executed by the database |
| 12,656 beers | Wikiliq snapshot (CC0), already embedded, HNSW index built |

The interesting function is `embed(text)`. It is written in `plpython3u`, it
loads the ONNX model into the backend on first use, and it returns 384 numbers.
Everything else is ordinary SQL:

```sql
SELECT embed('lemon');
SELECT * FROM search('dark roasty coffee chocolate');
SELECT * FROM similar_to(10462);
\sf search
```

## The exercises

| File | What it teaches | Time |
|---|---|---|
| `00_check.sql` | your database is ready | 2 min |
| `01_operators.sql` | how vectors are compared | 5 min |
| `02_search.sql` | search in your own words | 10 min |
| `03_indexes.sql` | brute force vs HNSW | 10 min |
| `04_sharp_edges.sql` | how approximate search loses rows | 10 min |
| `05_keep_it_fresh.sql` | new rows, new vectors, automatically | 8 min |
| `06_ivfflat.sql` | homework: a different index | - |
| `07_similarity_limits.sql` | homework: similar is not the same as logical | - |

Run one with `\i /workshop/02_search.sql`. They are all re-runnable.

## Prefer a GUI?

Connect DBeaver, pgAdmin or DataGrip to:

```
postgresql://beer:beer@localhost:5432/beer
```

## When something goes wrong

**Port 5432 is already in use.** You already run PostgreSQL. Use another port:

```bash
docker run -d --name beer -p 5433:5432 ghcr.io/pashagolub/hops-n-vectors:pg18
```

`docker exec -it beer psql` is unaffected; a GUI would use port 5433.

**"the input device is not a TTY"** in Git Bash on Windows. Use Windows Terminal
or PowerShell, or prefix the command with `winpty`.

**The name "beer" is already in use**, or the checks report `MISSING`. Start over:

```bash
docker rm -fv beer
docker run -d --name beer -p 5432:5432 ghcr.io/pashagolub/hops-n-vectors:pg18
```

**No Docker on your laptop.** Use a browser instead - see below. Failing that,
pair up with a neighbour; everything is a psql session, so watching costs you
nothing.

## Running it in a browser instead

You do not have to install anything. [Google Cloud Shell](https://shell.cloud.google.com)
is free with a Google account and has Docker preinstalled. Open it and run the
same two commands:

```bash
docker run -d --name beer ghcr.io/pashagolub/hops-n-vectors:pg18
docker exec -it beer psql
```

There is a second reason to consider this even if you do have Docker: the image
is pulled over Google's network, not the conference Wi-Fi. On a busy conference
day that is often the faster path.

What to know before you rely on it:

- It needs a Google account, and some corporate accounts have Cloud Shell disabled.
- Free tier is 50 hours per week; your `$HOME` is 5 GB and persists, but the
  container does not - when the session ends you re-run `docker run`.
- Skip `-p 5432:5432`. There is no local GUI to connect, and `docker exec` is
  all you need.

## No network at all?

Ask for the USB stick, then:

```bash
docker load -i hops-n-vectors-pg18-amd64.tar.gz
```

Use the `arm64` file on an Apple Silicon Mac.

## Afterwards

Everything here is MIT licensed and lives at
<https://github.com/pashagolub/hops-n-vectors>. The dataset is the Wikiliq
alcohol snapshot (CC0). The model is Apache 2.0.

Keeping it: `docker start beer`. Removing it: `docker rm -fv beer`.
