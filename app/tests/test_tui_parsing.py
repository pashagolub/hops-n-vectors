"""Unit tests for hopsnvectors.tui — pure logic only (no DB, no model, no network)."""

from __future__ import annotations

import pytest
from hopsnvectors.tui import _print_results, _truncate, parse_command, run_query_json

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



# ---------------------------------------------------------------------------
# _print_results
# ---------------------------------------------------------------------------


def test_print_results_empty(capsys):
    _print_results([])
    out = capsys.readouterr().out
    assert "No results" in out


def test_print_results_single_row(capsys):
    row = {
        "beer_name": "Lemon Wheat",
        "style": "Wheat",
        "distance": 0.123,
        "info": "Citrus lemon zesty beer",
    }
    _print_results([row])
    out = capsys.readouterr().out
    assert "Lemon Wheat" in out
    assert "0.123" in out
