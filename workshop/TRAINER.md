# Trainer guide - WAWTech 2026, Warsaw

50 minutes, hard stop. Attendees are on chairs with laptops and unreliable
Wi-Fi. You are on stage with power, a table and a network.

The through-line: **we build a beer sommelier that keeps itself up to date,
and it never leaves PostgreSQL.** Every chapter adds one capability and ends
with something on their own screen.

## Run sheet

| Min | Chapter | You say | They run |
|---|---|---|---|
| 0-3 | Boarding | "One command. If it fails, put your hand up and a neighbour's screen is fine." | `docker run`, `\i /workshop/00_check.sql` |
| 3-8 | Why not LIKE | "`LIKE '%lemon%'` finds the word. We want the taste." | `01_operators.sql` |
| 8-20 | Teach it to read | The centrepiece. `embed()` is Python inside the backend. Then hand the room the keyboard. | `02_search.sql`, then their own queries |
| 20-30 | Make it fast | Seq Scan on 12,656 rows, then the graph. Read the two timings aloud. | `03_indexes.sql` |
| 30-40 | Sharp edges | The 0-rows moment. Let it land before you fix it. | `04_sharp_edges.sql` |
| 40-47 | Keep it alive | They brew a beer, the database learns it. | `05_keep_it_fresh.sql` |
| 47-50 | Close | Links, homework, where to find you. | - |

If you are running late, cut chapter 3 to the two EXPLAIN outputs and skip the
index-size query. Never cut chapter 5 - it is the payoff.

## Pre-flight

- [ ] `docker pull ghcr.io/pashagolub/hops-n-vectors:pg18` on the presenter laptop
- [ ] Rehearse once with Wi-Fi **off**
- [ ] **Walk the Cloud Shell path yourself once**, start to finish, and note how
      long the pull takes. Open <https://shell.cloud.google.com>, then
      `docker run -d --name beer ghcr.io/pashagolub/hops-n-vectors:pg18` and
      `docker exec -it beer psql`. You will be recommending it from the stage;
      do not recommend something you have not run. Check in particular that the
      first `embed()` is not painfully slow on their smaller VM.
- [ ] `docker rm -fv beer` then a fresh `docker run`, so your timings match theirs
- [ ] USB sticks prepared (`make workshop-save`), amd64 and arm64, with the README
- [ ] Ask the organisers to post the pre-pull command in the app the day before
- [ ] Terminal font large enough that the back row can read a distance column

## The moments that work

**Chapter 2, after `search('dark roasty coffee chocolate')`.** Every result is a
stout. Then: "Now look at the descriptions. Nobody wrote 'roasty' in some of
them." That is the whole pitch in one screen.

**Chapter 2, `similar_to(10462)`.** Zywiec Lager returns Zamkowe, Kopernik,
Tyskie. "The model has reinvented the Polish supermarket shelf." Ask who drank
one of those this week.

**Chapter 2, `\sf search`.** Six lines of SQL. "This is the entire application.
There is no service. There is no Python process. There is a database."

**Chapter 4A.** The query returns zero rows with no error. Pause. "This is the
bug you ship, and your tests pass." Then one `SET` fixes it.

**Chapter 4B.** The kielbasa question returns kombucha. Own it - it is honest,
and the fix is a `WHERE` clause. Embeddings rank; SQL knows facts.

**Chapter 5.** They insert their own beer, it is invisible, then a scheduled job
inside the database gives it a vector. Ask someone to read their beer's
description out loud first.

## Timings on reference hardware

| | |
|---|---|
| `docker run` to healthy | 12-15 s |
| first `embed()` in a session | ~430 ms (model load) |
| later `embed()` | 5-10 ms |
| `search()` with HNSW | under 20 ms |
| HNSW build over 12,656 rows | ~1 s |
| whole-corpus re-embed (not done live) | ~3 min |

## If it goes wrong

- Someone's container never goes healthy: `docker rm -fv beer` and rerun. Do not
  debug one laptop on stage; pair them up and move on.
- Git Bash TTY error: Windows Terminal, or `winpty`.
- Port clash: `-p 5433:5432`.
- Room-wide Wi-Fi failure: USB sticks, and keep talking - the deck stands alone.
- Someone has no Docker, or a locked-down laptop: send them to
  <https://shell.cloud.google.com>. Say it once at minute zero, so the people
  who need it start their pull immediately rather than at minute fifteen.
- GitHub Codespaces also works in principle, but Docker inside a codespace needs
  a devcontainer feature enabled, so do not offer it from the stage unless you
  have added a `.devcontainer/` to the repo and tested it.

## Facts worth having ready

- 12,656 beers, Wikiliq snapshot (CC0), 1,196 of them list food pairings.
- 181 beers are above 12% ABV - that is why chapter 4 loses its rows.
- The model is 34 MB quantized; the fp32 original is 133 MB.
- 384 dimensions, cosine distance, `ef_search` defaults to 40.
- The whole image is 277 MB compressed.

## Questions you will get

**"Why not a real vector database?"** You already run PostgreSQL. One system,
one backup, one transaction, joins to your actual data. Come back when you have
a billion vectors and a latency budget.

**"Does this scale?"** HNSW does, to tens of millions per node. The in-database
model is fine for search-time embedding; bulk embedding of huge corpora belongs
in a batch job outside the database.

**"Which model in production?"** Something stronger than 34 MB, and measure
recall on your own data. The pattern does not change, only the file.

**"What about Polish?"** This model is English. Multilingual models of the same
384 dimensions exist and drop straight in - the schema does not change. I tested
one; it was better at flavours and worse at seasons. Measure on your data.

**"GDPR / data locality?"** Nothing left this laptop. That is the point.
