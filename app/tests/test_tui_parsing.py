"""Unit tests for hopsnvectors.tui — pure logic only (no DB, no model, no network)."""

from __future__ import annotations

import json
import os

import pytest

from hopsnvectors.tui import (
    _clear_screen,
    _print_results,
    _truncate,
    main,
    parse_command,
    repl,
    run_query_json,
)

# ---------------------------------------------------------------------------
# parse_command — free-text prompts
# ---------------------------------------------------------------------------


def test_free_text_returns_prompt():
    cmd = parse_command("hoppy lager")
    assert cmd.prompt == "hoppy lager"
    assert cmd.error is None


def test_free_text_strips_whitespace():
    cmd = parse_command("  fruity IPA  ")
    assert cmd.prompt == "fruity IPA"


def test_free_text_non_ascii_accepted():
    cmd = parse_command("Weißbier zitrone")
    assert cmd.prompt == "Weißbier zitrone"
    assert cmd.error is None


def test_exactly_4000_chars_accepted():
    prompt = "a" * 4000
    cmd = parse_command(prompt)
    assert cmd.prompt == prompt
    assert cmd.error is None


def test_prompt_over_4000_chars_returns_error():
    prompt = "a" * 4001
    cmd = parse_command(prompt)
    assert cmd.error is not None
    assert "4001" in cmd.error or "4000" in cmd.error


# ---------------------------------------------------------------------------
# parse_command — empty / whitespace input
# ---------------------------------------------------------------------------


def test_empty_string_returns_error():
    cmd = parse_command("")
    assert cmd.error is not None
    assert cmd.prompt is None


def test_whitespace_only_returns_error():
    cmd = parse_command("   ")
    assert cmd.error is not None


# ---------------------------------------------------------------------------
# parse_command — :like
# ---------------------------------------------------------------------------


def test_like_valid_id():
    cmd = parse_command(":like 42")
    assert cmd.like_id == 42
    assert cmd.error is None


def test_like_no_args_returns_error():
    cmd = parse_command(":like")
    assert cmd.error is not None


def test_like_non_numeric_arg_returns_error():
    cmd = parse_command(":like abc")
    assert cmd.error is not None


def test_like_too_many_args_returns_error():
    cmd = parse_command(":like 1 2")
    assert cmd.error is not None


def test_like_case_insensitive():
    cmd = parse_command(":LIKE 1")
    assert cmd.like_id == 1
    assert cmd.error is None


# ---------------------------------------------------------------------------
# parse_command — :top
# ---------------------------------------------------------------------------


def test_top_valid_value():
    cmd = parse_command(":top 10")
    assert cmd.top == 10
    assert cmd.error is None


def test_top_boundary_min():
    cmd = parse_command(":top 1")
    assert cmd.top == 1
    assert cmd.error is None


def test_top_boundary_max():
    cmd = parse_command(":top 50")
    assert cmd.top == 50
    assert cmd.error is None


def test_top_zero_returns_error():
    cmd = parse_command(":top 0")
    assert cmd.error is not None


def test_top_over_max_returns_error():
    cmd = parse_command(":top 51")
    assert cmd.error is not None


def test_top_non_numeric_returns_error():
    cmd = parse_command(":top abc")
    assert cmd.error is not None


def test_top_no_arg_returns_error():
    cmd = parse_command(":top")
    assert cmd.error is not None


# ---------------------------------------------------------------------------
# parse_command — action commands
# ---------------------------------------------------------------------------


def test_explain_action():
    cmd = parse_command(":explain")
    assert cmd.action == "explain"
    assert cmd.error is None


def test_help_action():
    cmd = parse_command(":help")
    assert cmd.action == "help"
    assert cmd.error is None


def test_quit_action():
    cmd = parse_command(":quit")
    assert cmd.action == "quit"


def test_exit_action():
    cmd = parse_command(":exit")
    assert cmd.action == "quit"


def test_q_action():
    cmd = parse_command(":q")
    assert cmd.action == "quit"


def test_quit_case_insensitive():
    cmd = parse_command(":Quit")
    assert cmd.action == "quit"
    assert cmd.error is None


# ---------------------------------------------------------------------------
# parse_command — unknown command
# ---------------------------------------------------------------------------


def test_unknown_command_returns_error_mentioning_help():
    cmd = parse_command(":foo")
    assert cmd.error is not None
    assert ":help" in cmd.error


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------


def test_truncate_short_text_unchanged():
    assert _truncate("short", width=60) == "short"


def test_truncate_text_at_exact_width_unchanged():
    text = "x" * 60
    assert _truncate(text, width=60) == text


def test_truncate_long_text_cut_with_ellipsis():
    text = "a" * 100
    result = _truncate(text, width=60)
    assert len(result) == 60
    assert result.endswith("…")


def test_truncate_none_returns_empty_string():
    assert _truncate(None) == ""


def test_truncate_newlines_replaced_by_spaces():
    result = _truncate("line one\nline two", width=60)
    assert "\n" not in result
    assert " " in result


def test_truncate_default_width_is_60():
    text = "b" * 61
    result = _truncate(text)
    assert len(result) == 60


# ---------------------------------------------------------------------------
# run_query_json — argument validation only (no DB)
# ---------------------------------------------------------------------------


def test_run_query_json_empty_string_raises_system_exit():
    with pytest.raises(SystemExit):
        run_query_json("", top=5)


def test_run_query_json_serializes_rows(monkeypatch):
    class _S:
        def by_prompt(self, prompt, top):
            return [{"id": 1, "beer_name": "X", "distance": 0.5}]

    monkeypatch.setattr("hopsnvectors.tui.Searcher", _S)
    data = json.loads(run_query_json("hoppy", 5))
    assert data[0]["distance"] == 0.5
    assert data[0]["beer_name"] == "X"


# ---------------------------------------------------------------------------
# main — argument dispatch (no DB)
# ---------------------------------------------------------------------------


def test_main_query_without_json_errors():
    with pytest.raises(SystemExit):
        main(["--query", "hoppy"])


def test_main_top_out_of_range_errors():
    with pytest.raises(SystemExit):
        main(["--top", "999"])


def test_main_query_json_prints_result(monkeypatch, capsys):
    monkeypatch.setattr("hopsnvectors.tui.run_query_json", lambda q, t: '{"ok":1}')
    main(["--query", "hoppy", "--json"])
    assert '{"ok":1}' in capsys.readouterr().out


def test_main_no_args_starts_repl(monkeypatch):
    called = {}
    monkeypatch.setattr("hopsnvectors.tui.repl", lambda: called.setdefault("ran", True))
    main([])
    assert called["ran"] is True



# ---------------------------------------------------------------------------
# _print_results
# ---------------------------------------------------------------------------


def test_print_results_empty(capsys):
    _print_results([])
    out = capsys.readouterr().out
    assert "No results" in out


def test_print_results_single_row(capsys):
    row = {
        "id": 42,
        "beer_name": "Lemon Wheat",
        "style": "Wheat",
        "distance": 0.123,
        "info": "Citrus lemon zesty beer",
    }
    _print_results([row])
    out = capsys.readouterr().out
    assert "Lemon Wheat" in out
    assert "0.123" in out
    assert "id=42" in out


def test_print_results_long_header_truncates(capsys, monkeypatch):
    monkeypatch.setattr(
        "hopsnvectors.tui.shutil.get_terminal_size",
        lambda fallback=(80, 24): os.terminal_size((40, 24)),
    )
    row = {
        "id": 1,
        "beer_name": "A" * 80,
        "style": "B" * 40,
        "distance": 0.1,
        "info": "",
    }
    _print_results([row])
    out = capsys.readouterr().out
    assert "…" in out


# ---------------------------------------------------------------------------
# _clear_screen
# ---------------------------------------------------------------------------


def test_clear_screen_emits_escape(capsys):
    _clear_screen()
    assert "\033[2J" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# repl — interactive loop driven by a fake Searcher and scripted input
# ---------------------------------------------------------------------------


class _FakeSearcher:
    """Stand-in Searcher: records calls, returns canned rows, no DB/model."""

    def __init__(self, rows=None):
        self.rows = rows if rows is not None else []
        self.calls = []

    def by_prompt(self, prompt, top):
        self.calls.append(("by_prompt", prompt, top))
        return self.rows

    def by_beer(self, beer_id, top):
        self.calls.append(("by_beer", beer_id, top))
        if beer_id == 999:
            raise LookupError("Beer 999 not found.")
        return self.rows

    def explain_prompt(self, prompt, top):
        self.calls.append(("explain_prompt", prompt, top))
        return "PLAN prompt"

    def explain_beer(self, beer_id, top):
        self.calls.append(("explain_beer", beer_id, top))
        return "PLAN beer"


def _feed_input(monkeypatch, lines):
    """Patch builtins.input to yield each line, then raise EOFError."""
    it = iter(lines)

    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration as exc:
            raise EOFError from exc

    monkeypatch.setattr("builtins.input", fake_input)


def test_repl_eof_exits_immediately(monkeypatch, capsys):
    _feed_input(monkeypatch, [])
    repl(_FakeSearcher())
    assert "Hops'n'Vectors" in capsys.readouterr().out


def test_repl_quit_command_exits(monkeypatch, capsys):
    searcher = _FakeSearcher()
    _feed_input(monkeypatch, [":quit"])
    repl(searcher)
    assert searcher.calls == []


def test_repl_help_prints_commands(monkeypatch, capsys):
    _feed_input(monkeypatch, [":help"])
    repl(_FakeSearcher())
    assert ":like" in capsys.readouterr().out


def test_repl_cls_clears_screen(monkeypatch, capsys):
    _feed_input(monkeypatch, [":cls"])
    repl(_FakeSearcher())
    assert "\033[2J" in capsys.readouterr().out


def test_repl_empty_line_shows_error(monkeypatch, capsys):
    _feed_input(monkeypatch, [""])
    repl(_FakeSearcher())
    assert "Please enter" in capsys.readouterr().out


def test_repl_top_sets_count(monkeypatch, capsys):
    searcher = _FakeSearcher()
    _feed_input(monkeypatch, [":top 3", "hoppy"])
    repl(searcher)
    assert ("by_prompt", "hoppy", 3) in searcher.calls
    assert "Result count set to 3" in capsys.readouterr().out


def test_repl_prompt_search_prints_results(monkeypatch, capsys):
    rows = [{"id": 1, "beer_name": "Zest", "style": "IPA", "distance": 0.2, "info": ""}]
    searcher = _FakeSearcher(rows)
    _feed_input(monkeypatch, ["lemon"])
    repl(searcher)
    out = capsys.readouterr().out
    assert "Zest" in out
    assert ("by_prompt", "lemon", 5) in searcher.calls


def test_repl_like_search_calls_by_beer(monkeypatch, capsys):
    searcher = _FakeSearcher()
    _feed_input(monkeypatch, [":like 7"])
    repl(searcher)
    assert ("by_beer", 7, 5) in searcher.calls


def test_repl_unknown_command_shows_error(monkeypatch, capsys):
    _feed_input(monkeypatch, [":nope"])
    repl(_FakeSearcher())
    assert ":help" in capsys.readouterr().out


def test_repl_lookup_error_is_reported(monkeypatch, capsys):
    searcher = _FakeSearcher()
    _feed_input(monkeypatch, [":like 999"])
    repl(searcher)
    assert "not found" in capsys.readouterr().out


def test_repl_explain_toggle_runs_explain_prompt(monkeypatch, capsys):
    searcher = _FakeSearcher()
    _feed_input(monkeypatch, [":explain", "hoppy"])
    repl(searcher)
    out = capsys.readouterr().out
    assert "EXPLAIN ANALYZE output on" in out
    assert "PLAN prompt" in out
    assert ("explain_prompt", "hoppy", 5) in searcher.calls


def test_repl_explain_toggle_runs_explain_beer(monkeypatch, capsys):
    searcher = _FakeSearcher()
    _feed_input(monkeypatch, [":explain", ":like 4"])
    repl(searcher)
    assert ("explain_beer", 4, 5) in searcher.calls
    assert "PLAN beer" in capsys.readouterr().out


def test_repl_keyboard_interrupt_exits(monkeypatch, capsys):
    def raise_interrupt(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_interrupt)
    repl(_FakeSearcher())
    # Banner still printed before the interrupt breaks the loop.
    assert "Hops'n'Vectors" in capsys.readouterr().out
