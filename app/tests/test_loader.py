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
        "Style": "IPA",
        "Brewery": "Test Brewery",
        "Beer Name (Full)": "Test Brewery Test Beer",
        "Description": "Hoppy and bitter",
        "ABV": "6.0",
        "Min IBU": "40",
        "Max IBU": "60",
        "Astringency": "10",
        "Body": "20",
        "Alcohol": "15",
        "Bitter": "70",
        "Sweet": "30",
        "Sour": "5",
        "Salty": "0",
        "Fruits": "10",
        "Hoppy": "80",
        "Spices": "5",
        "Malty": "20",
        "review_aroma": "3.5",
        "review_appearance": "3.8",
        "review_palate": "3.6",
        "review_taste": "3.7",
        "review_overall": "3.8",
        "number_of_reviews": "100",
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
    rows, dupes = _read_and_deduplicate(path)
    assert len(rows) == 1
    assert dupes == 0


def test_utf8_bom_header_accepted(tmp_path):
    """CSV with UTF-8 BOM on the first header field must still validate."""
    path = _make_csv([_default_row()], tmp_path, encoding="utf-8-sig")
    rows, _ = _read_and_deduplicate(path)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Deduplication on natural key (edge case 2)
# ---------------------------------------------------------------------------

def test_duplicates_are_counted_and_removed(tmp_path):
    row1 = _default_row(Name="Amber", Brewery="A", Style="Altbier")
    row2 = _default_row(Name="Amber", Brewery="A", Style="Altbier", Description="dup")
    path = _make_csv([row1, row2], tmp_path)
    rows, dupes = _read_and_deduplicate(path)
    assert len(rows) == 1
    assert dupes == 1


def test_different_breweries_not_deduplicated(tmp_path):
    row1 = _default_row(Name="Amber", Brewery="Brewery A")
    row2 = _default_row(Name="Amber", Brewery="Brewery B")
    path = _make_csv([row1, row2], tmp_path)
    rows, dupes = _read_and_deduplicate(path)
    assert len(rows) == 2
    assert dupes == 0


def test_different_styles_not_deduplicated(tmp_path):
    row1 = _default_row(Name="Lager", Style="American Lager")
    row2 = _default_row(Name="Lager", Style="German Lager")
    path = _make_csv([row1, row2], tmp_path)
    rows, dupes = _read_and_deduplicate(path)
    assert len(rows) == 2
    assert dupes == 0


# ---------------------------------------------------------------------------
# Non-ASCII names (edge case 3)
# ---------------------------------------------------------------------------

def test_non_ascii_beer_name_preserved(tmp_path):
    path = _make_csv([_default_row(Name="K\u00f6stritzer Schwarzbier")], tmp_path)
    rows, _ = _read_and_deduplicate(path)
    assert rows[0]["Name"] == "K\u00f6stritzer Schwarzbier"


# ---------------------------------------------------------------------------
# Empty / missing description (edge case 3)
# ---------------------------------------------------------------------------

def test_empty_description_row_is_accepted(tmp_path):
    path = _make_csv([_default_row(Description="")], tmp_path)
    rows, _ = _read_and_deduplicate(path)
    assert len(rows) == 1


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

