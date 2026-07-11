"""Interactive beer-recommendation TUI plus non-interactive CI mode.

Interactive commands (spec §4.5):
  free text      embed prompt, show top-N similar beers by cosine distance
  :like <id>     "more like this" for beer <id> (excludes the beer itself)
  :top <n>       set result count N (1-50)
  :explain       toggle EXPLAIN ANALYZE output for executed searches
  :help          show commands
  :quit / Ctrl-D exit

Non-interactive mode (CI/E2E):
  python -m hopsnvectors.tui --query <text> --json [--top n]
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

_MAX_PROMPT_LEN = 4_000
_MIN_TOP, _MAX_TOP = 1, 50
_DEFAULT_TOP = int(os.environ.get("TOP_N_DEFAULT", "5"))

_BANNER = """\
🍺 Hops'n'Vectors — pgvector beer recommender
Please enjoy responsibly: this demo is for informational and entertainment
purposes only and does not encourage alcohol consumption.
Type :help for commands.
"""

_HELP = """\
Commands:
  <free text>   search beers similar to your prompt (e.g. "lemon")
  :like <id>    more beers like beer <id>
  :top <n>      set result count (1-50)
  :explain      toggle EXPLAIN ANALYZE output
  :help         this help
  :quit         exit (also Ctrl-D)
"""

# Parameterized query contracts (spec §4.3, SEC-003).
_PROMPT_SQL = """\
SELECT id, beer_name, brewery, style, info,
       embedding <=> %s AS distance
FROM beers
ORDER BY embedding <=> %s
LIMIT %s
"""

_LIKE_SQL = """\
SELECT b.id, b.beer_name, b.brewery, b.style, b.info,
       b.embedding <=> s.embedding AS distance
FROM beers b, (SELECT embedding FROM beers WHERE id = %s) s
WHERE b.id <> %s
ORDER BY b.embedding <=> s.embedding
LIMIT %s
"""


@dataclass
class Command:
    """Parsed user input: exactly one of prompt/like_id/top/action is set."""

    prompt: str | None = None
    like_id: int | None = None
    top: int | None = None
    action: str | None = None  # "explain" | "help" | "quit"
    error: str | None = None


def parse_command(line: str) -> Command:
    """Parse one line of user input into a Command (pure; unit-testable)."""
    line = line.strip()
    if not line:
        return Command(error="Please enter a prompt or command (:help for help).")

    if not line.startswith(":"):
        if len(line) > _MAX_PROMPT_LEN:
            return Command(
                error=f"Prompt too long ({len(line)} chars, max {_MAX_PROMPT_LEN})."
            )
        return Command(prompt=line)

    parts = line.split()
    cmd, args = parts[0].lower(), parts[1:]

    if cmd == ":like":
        if len(args) != 1 or not args[0].lstrip("-").isdigit():
            return Command(error="Usage: :like <beer id>")
        return Command(like_id=int(args[0]))
    if cmd == ":top":
        if len(args) != 1 or not args[0].lstrip("-").isdigit():
            return Command(error=f"Usage: :top <n>  ({_MIN_TOP}-{_MAX_TOP})")
        n = int(args[0])
        if not _MIN_TOP <= n <= _MAX_TOP:
            return Command(error=f"N must be between {_MIN_TOP} and {_MAX_TOP}.")
        return Command(top=n)
    if cmd == ":explain":
        return Command(action="explain")
    if cmd == ":help":
        return Command(action="help")
    if cmd in (":quit", ":exit", ":q"):
        return Command(action="quit")
    return Command(error=f"Unknown command {cmd}.  Type :help for help.")


def _truncate(text: str | None, width: int = 60) -> str:
    text = (text or "").replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


class Searcher:
    """Lazy model + connection holder executing the §4.3 query contracts."""

    def __init__(self) -> None:
        self._model = None
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            from pgvector.psycopg import register_vector  # noqa: PLC0415

            from hopsnvectors.db import get_connection  # noqa: PLC0415

            self._conn = get_connection(autocommit=True)
            register_vector(self._conn)
        return self._conn

    def _embed(self, text: str):
        if self._model is None:
            from hopsnvectors.embedder import _load_model  # noqa: PLC0415

            self._model = _load_model()
        return self._model.encode(text)

    def by_prompt(self, prompt: str, top: int) -> list[dict]:
        vec = self._embed(prompt)
        return self._run(_PROMPT_SQL, (vec, vec, top))

    def by_beer(self, beer_id: int, top: int) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM beers WHERE id = %s", (beer_id,))
            if cur.fetchone() is None:
                raise LookupError(f"Beer {beer_id} not found.")
        return self._run(_LIKE_SQL, (beer_id, beer_id, top))

    def _run(self, sql: str, params: tuple) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def explain(self, sql: str, params: tuple) -> str:
        with self.conn.cursor() as cur:
            cur.execute("EXPLAIN ANALYZE " + sql, params)
            return "\n".join(row[0] for row in cur.fetchall())

    def explain_prompt(self, prompt: str, top: int) -> str:
        vec = self._embed(prompt)
        return self.explain(_PROMPT_SQL, (vec, vec, top))

    def explain_beer(self, beer_id: int, top: int) -> str:
        return self.explain(_LIKE_SQL, (beer_id, beer_id, top))


def _print_results(rows: list[dict]) -> None:
    if not rows:
        print("No results.")
        return
    for i, r in enumerate(rows, 1):
        print(
            f"{i:3d}. {r['beer_name']:<30.30s} ({_truncate(r['style'], 20)})"
            f"  d={r['distance']:.3f}  \"{_truncate(r['info'])}\""
        )


def repl(searcher: Searcher | None = None) -> None:
    searcher = searcher or Searcher()
    top = _DEFAULT_TOP
    explain = False
    print(_BANNER)

    while True:
        try:
            line = input("🍺 > ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        cmd = parse_command(line)
        if cmd.error:
            print(cmd.error)
            continue
        if cmd.action == "quit":
            break
        if cmd.action == "help":
            print(_HELP)
            continue
        if cmd.action == "explain":
            explain = not explain
            print(f"EXPLAIN ANALYZE output {'on' if explain else 'off'}.")
            continue
        if cmd.top is not None:
            top = cmd.top
            print(f"Result count set to {top}.")
            continue

        try:
            if cmd.like_id is not None:
                _print_results(searcher.by_beer(cmd.like_id, top))
                if explain:
                    print(searcher.explain_beer(cmd.like_id, top))
            else:
                _print_results(searcher.by_prompt(cmd.prompt, top))
                if explain:
                    print(searcher.explain_prompt(cmd.prompt, top))
        except LookupError as exc:
            print(exc)


def run_query_json(query: str, top: int) -> str:
    """Non-interactive mode: return search results as a JSON string."""
    cmd = parse_command(query)
    if cmd.error or cmd.prompt is None:
        raise SystemExit(f"ERROR: {cmd.error or 'not a free-text prompt'}")
    rows = Searcher().by_prompt(cmd.prompt, top)
    for r in rows:
        r["distance"] = float(r["distance"])
    return json.dumps(rows, ensure_ascii=False)


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Beer recommendation TUI.")
    parser.add_argument("--query", metavar="TEXT", help="non-interactive prompt search")
    parser.add_argument("--json", action="store_true", help="emit JSON (with --query)")
    parser.add_argument(
        "--top", type=int, default=_DEFAULT_TOP, metavar="N",
        help=f"result count {_MIN_TOP}-{_MAX_TOP} (default {_DEFAULT_TOP})",
    )
    args = parser.parse_args(argv)

    if not _MIN_TOP <= args.top <= _MAX_TOP:
        parser.error(f"--top must be between {_MIN_TOP} and {_MAX_TOP}")

    if args.query is not None:
        if not args.json:
            parser.error("--query requires --json (non-interactive CI mode)")
        print(run_query_json(args.query, args.top))
        return

    repl()


if __name__ == "__main__":
    main()
