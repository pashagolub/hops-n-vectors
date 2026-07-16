"""Unit tests for hopsnvectors.loader."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from hopsnvectors import loader as loader_module
from hopsnvectors.loader import (
    REQUIRED_COLUMNS,
    _is_lfs_pointer,
    _read_and_deduplicate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_csv(
    rows: list[dict],
    tmp_path: Path,
    name: str = "test.csv",
    encoding: str = "utf-8",
) -> Path:
    """Write a well-formed CSV with all required columns to *tmp_path*."""
    cols = sorted(REQUIRED_COLUMNS)
    path = tmp_path / name
    with path.open("w", newline="", encoding=encoding) as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _default_row(**overrides) -> dict:
    base: dict = {
        "Name": "Test Beer",
        "Country": "United States",
        "Brand": "Test Brewery",
        "Categories": "ALE, IPA",
        "Tasting Notes": "Hoppy, Citrus",
        "ABV": "6%",
        "IBU": "45",
        "Food Pairing": "Cheese - Hard Aged",
        "Rating": "4.2",
        "Rate Count": "100",
        "Description": "Hoppy and bitter",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# LFS pointer detection
# ---------------------------------------------------------------------------

def test_lfs_pointer_detected(tmp_path):
    lfs = tmp_path / "lfs.csv"
    lfs.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:abc123\nsize 12345\n"
    )
    assert _is_lfs_pointer(lfs) is True


def test_regular_file_not_detected_as_lfs(tmp_path):
    regular = tmp_path / "regular.csv"
    regular.write_text("Name,Style\nBeer,IPA\n")
    assert _is_lfs_pointer(regular) is False


# ---------------------------------------------------------------------------
# Column validation (SEC-002)
# ---------------------------------------------------------------------------

def test_missing_column_raises_system_exit(tmp_path):
    cols = sorted(REQUIRED_COLUMNS - {"Description"})
    path = tmp_path / "bad.csv"
    with path.open("w", newline="") as fh:
        csv.DictWriter(fh, fieldnames=cols).writeheader()
    with pytest.raises(SystemExit, match="missing required columns"):
        _read_and_deduplicate(path)


def test_good_csv_loads_without_error(tmp_path):
    path = _make_csv([_default_row()], tmp_path)
    rows, dupes, skipped = _read_and_deduplicate(path)
    assert len(rows) == 1
    assert dupes == 0
    assert skipped == 0


def test_utf8_bom_header_accepted(tmp_path):
    """CSV with UTF-8 BOM on the first header field must still validate."""
    path = _make_csv([_default_row()], tmp_path, encoding="utf-8-sig")
    rows, _, _ = _read_and_deduplicate(path)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Deduplication on natural key (edge case 2)
# ---------------------------------------------------------------------------

def test_duplicates_are_counted_and_removed(tmp_path):
    row1 = _default_row(Name="Amber", Brand="A", Categories="Altbier")
    row2 = _default_row(Name="Amber", Brand="A", Categories="Altbier", Description="dup")
    path = _make_csv([row1, row2], tmp_path)
    rows, dupes, _ = _read_and_deduplicate(path)
    assert len(rows) == 1
    assert dupes == 1


def test_different_breweries_not_deduplicated(tmp_path):
    row1 = _default_row(Name="Amber", Brand="Brewery A")
    row2 = _default_row(Name="Amber", Brand="Brewery B")
    path = _make_csv([row1, row2], tmp_path)
    rows, dupes, _ = _read_and_deduplicate(path)
    assert len(rows) == 2
    assert dupes == 0


def test_different_styles_not_deduplicated(tmp_path):
    row1 = _default_row(Name="Lager", Categories="American Lager")
    row2 = _default_row(Name="Lager", Categories="German Lager")
    path = _make_csv([row1, row2], tmp_path)
    rows, dupes, _ = _read_and_deduplicate(path)
    assert len(rows) == 2
    assert dupes == 0


# ---------------------------------------------------------------------------
# Keg/barrel SKU filtering
# ---------------------------------------------------------------------------

def test_keg_rows_are_skipped(tmp_path):
    rows_in = [
        _default_row(),
        _default_row(Name="Test Beer 1/6 Barrel"),
        _default_row(Name="Test Beer \u2159 Barrel"),
        _default_row(
            Name="Other Beer Keggy",
            Description="Kegs are intended for Kegerator use only. TAP NOT INCLUDED.",
        ),
    ]
    path = _make_csv(rows_in, tmp_path)
    rows, _, skipped = _read_and_deduplicate(path)
    assert len(rows) == 1
    assert skipped == 3


def test_rows_without_name_are_skipped(tmp_path):
    path = _make_csv([_default_row(Name="")], tmp_path)
    rows, _, skipped = _read_and_deduplicate(path)
    assert len(rows) == 0
    assert skipped == 1


# ---------------------------------------------------------------------------
# Non-ASCII names (edge case 3)
# ---------------------------------------------------------------------------

def test_non_ascii_beer_name_preserved(tmp_path):
    path = _make_csv([_default_row(Name="K\u00f6stritzer Schwarzbier")], tmp_path)
    rows, _, _ = _read_and_deduplicate(path)
    assert rows[0]["Name"] == "K\u00f6stritzer Schwarzbier"


# ---------------------------------------------------------------------------
# Empty / missing description (edge case 3)
# ---------------------------------------------------------------------------

def test_empty_description_row_is_accepted(tmp_path):
    path = _make_csv([_default_row(Description="")], tmp_path)
    rows, _, _ = _read_and_deduplicate(path)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Value parsing (percent-decorated ABV, ratings)
# ---------------------------------------------------------------------------

def test_percent_abv_parsed():
    from hopsnvectors.loader import _build_params
    params = _build_params(_default_row(ABV="8.5%"))
    assert params["abv"] == 8.5


def test_rating_and_rate_count_mapped():
    from hopsnvectors.loader import _build_params
    params = _build_params(_default_row(Rating="4.7", **{"Rate Count": "17"}))
    assert params["review_overall"] == 4.7
    assert params["number_of_reviews"] == 17


def test_info_includes_tasting_notes_and_country():
    from hopsnvectors.loader import _build_params
    params = _build_params(_default_row())
    assert "Hoppy, Citrus" in params["info"]
    assert "United States" in params["info"]
    assert "Test Beer" in params["info"]


# ---------------------------------------------------------------------------
# load() — pre-load validation (no DB required)
# ---------------------------------------------------------------------------

def test_load_aborts_on_missing_file(tmp_path):
    with pytest.raises(SystemExit, match="not found"):
        loader_module.load(tmp_path / "nonexistent.csv")


def test_load_aborts_on_lfs_pointer(tmp_path):
    lfs = tmp_path / "lfs.csv"
    lfs.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:x\n")
    with pytest.raises(SystemExit, match="Git-LFS"):
        loader_module.load(lfs)


def test_load_aborts_on_missing_column(tmp_path):
    cols = sorted(REQUIRED_COLUMNS - {"ABV"})
    path = tmp_path / "no_abv.csv"
    with path.open("w", newline="") as fh:
        csv.DictWriter(fh, fieldnames=cols).writeheader()
    with pytest.raises(SystemExit, match="missing required columns"):
        loader_module.load(path)

