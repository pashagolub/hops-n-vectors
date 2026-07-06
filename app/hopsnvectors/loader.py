"""Validate and idempotently load the bundled dataset CSV into the beers table."""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from hopsnvectors.db import get_connection
from hopsnvectors.textcompose import compose_info
from hopsnvectors.textcompose import text_hash as make_hash

# Default CSV path when running as a container (data/ is bind-mounted read-only).
_DEFAULT_CSV = Path("/data/beer_profile_and_ratings.csv")

# Provenance metadata written to dataset_meta on every load.
_SOURCE_URL = (
    "https://www.kaggle.com/datasets/ruthgn/beer-profile-and-ratings-data-set"
)
_LICENSE = "CC BY 4.0"
_SNAPSHOT_VERSION = "2024-01"

REQUIRED_COLUMNS = frozenset({
    "Name", "Style", "Brewery", "Beer Name (Full)", "Description",
    "ABV", "Min IBU", "Max IBU",
    "Astringency", "Body", "Alcohol", "Bitter", "Sweet", "Sour", "Salty",
    "Fruits", "Hoppy", "Spices", "Malty",
    "review_aroma", "review_appearance", "review_palate", "review_taste",
    "review_overall", "number_of_reviews",
})

# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _norm(value: str | None) -> str:
    """Strip UTF-8 BOM and surrounding whitespace."""
    return (value or "").lstrip("\ufeff").strip()


def _to_float(value: str) -> float | None:
    v = _norm(value)
    try:
        return float(v) if v else None
    except ValueError:
        return None


def _to_int(value: str) -> int | None:
    v = _norm(value)
    try:
        return int(float(v)) if v else None
    except ValueError:
        return None


def _is_lfs_pointer(path: Path) -> bool:
    """Return True if the file looks like a Git-LFS pointer (not real data)."""
    try:
        head = path.read_bytes()[:256].decode(errors="replace")
        return head.startswith("version https://git-lfs.github.com/spec/")
    except OSError:
        return False


def _read_and_deduplicate(path: Path) -> tuple[list[dict], int]:
    """Parse the CSV, normalise headers, and deduplicate on the natural key.

    Returns ``(unique_rows, duplicate_count)``.
    Aborts via ``SystemExit`` if required columns are missing (SEC-002).
    """
    with path.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise SystemExit("ERROR: CSV file appears to be empty. Load aborted.")

        # Normalise headers so BOM / whitespace variants still pass validation.
        headers = [_norm(h) for h in reader.fieldnames]
        missing = REQUIRED_COLUMNS - set(headers)
        if missing:
            raise SystemExit(
                f"ERROR: CSV is missing required columns: {sorted(missing)}\n"
                "Load aborted — no rows were inserted."
            )

        seen: dict[tuple[str, str, str], dict] = {}
        duplicates = 0
        for raw in reader:
            row = {_norm(k): _norm(v) for k, v in raw.items() if k is not None}
            key = (row["Name"], row["Brewery"], row["Style"])
            if key in seen:
                duplicates += 1
            else:
                seen[key] = row

    return list(seen.values()), duplicates


def _build_params(row: dict) -> dict:
    """Map a normalised CSV row dict to the SQL upsert parameter dict."""
    taste: dict[str, int | None] = {
        "astringency": _to_int(row.get("Astringency", "")),
        "body":        _to_int(row.get("Body", "")),
        "alcohol":     _to_int(row.get("Alcohol", "")),
        "bitter":      _to_int(row.get("Bitter", "")),
        "sweet":       _to_int(row.get("Sweet", "")),
        "sour":        _to_int(row.get("Sour", "")),
        "salty":       _to_int(row.get("Salty", "")),
        "fruits":      _to_int(row.get("Fruits", "")),
        "hoppy":       _to_int(row.get("Hoppy", "")),
        "spices":      _to_int(row.get("Spices", "")),
        "malty":       _to_int(row.get("Malty", "")),
    }
    info = compose_info(
        beer_name=row["Name"],
        style=row.get("Style"),
        description=row.get("Description"),
        taste=taste,
    )
    return {
        "beer_name":          row["Name"],
        "brewery":            row.get("Brewery") or None,
        "style":              row.get("Style") or None,
        "abv":                _to_float(row.get("ABV", "")),
        "min_ibu":            _to_int(row.get("Min IBU", "")),
        "max_ibu":            _to_int(row.get("Max IBU", "")),
        **taste,
        "review_aroma":       _to_float(row.get("review_aroma", "")),
        "review_appearance":  _to_float(row.get("review_appearance", "")),
        "review_palate":      _to_float(row.get("review_palate", "")),
        "review_taste":       _to_float(row.get("review_taste", "")),
        "review_overall":     _to_float(row.get("review_overall", "")),
        "number_of_reviews":  _to_int(row.get("number_of_reviews", "")),
        "info":               info,
        "text_hash":          make_hash(info),
    }


# All parameterised — no string interpolation of user data (SEC-003).
_UPSERT_SQL = """
INSERT INTO beers (
    beer_name, brewery, style, abv, min_ibu, max_ibu,
    astringency, body, alcohol, bitter, sweet, sour, salty,
    fruits, hoppy, spices, malty,
    review_aroma, review_appearance, review_palate, review_taste, review_overall,
    number_of_reviews, info, text_hash, updated_at
) VALUES (
    %(beer_name)s, %(brewery)s, %(style)s, %(abv)s, %(min_ibu)s, %(max_ibu)s,
    %(astringency)s, %(body)s, %(alcohol)s, %(bitter)s, %(sweet)s, %(sour)s,
    %(salty)s, %(fruits)s, %(hoppy)s, %(spices)s, %(malty)s,
    %(review_aroma)s, %(review_appearance)s, %(review_palate)s,
    %(review_taste)s, %(review_overall)s, %(number_of_reviews)s,
    %(info)s, %(text_hash)s, now()
)
ON CONFLICT (beer_name, brewery, style) DO UPDATE SET
    abv               = EXCLUDED.abv,
    min_ibu           = EXCLUDED.min_ibu,
    max_ibu           = EXCLUDED.max_ibu,
    astringency       = EXCLUDED.astringency,
    body              = EXCLUDED.body,
    alcohol           = EXCLUDED.alcohol,
    bitter            = EXCLUDED.bitter,
    sweet             = EXCLUDED.sweet,
    sour              = EXCLUDED.sour,
    salty             = EXCLUDED.salty,
    fruits            = EXCLUDED.fruits,
    hoppy             = EXCLUDED.hoppy,
    spices            = EXCLUDED.spices,
    malty             = EXCLUDED.malty,
    review_aroma      = EXCLUDED.review_aroma,
    review_appearance = EXCLUDED.review_appearance,
    review_palate     = EXCLUDED.review_palate,
    review_taste      = EXCLUDED.review_taste,
    review_overall    = EXCLUDED.review_overall,
    number_of_reviews = EXCLUDED.number_of_reviews,
    info              = EXCLUDED.info,
    text_hash         = EXCLUDED.text_hash,
    updated_at        = CASE
                          WHEN beers.info IS DISTINCT FROM EXCLUDED.info THEN now()
                          ELSE beers.updated_at
                        END
"""

# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def load(csv_path: Path = _DEFAULT_CSV) -> None:
    """Validate and upsert the dataset CSV into the ``beers`` table.

    Prints human-readable progress to stdout (REQ-011).  Aborts via
    ``SystemExit`` on any pre-load validation failure (SEC-002) so that
    partial loads never occur.
    """
    if not csv_path.exists():
        raise SystemExit(f"ERROR: Dataset not found at {csv_path}")

    if _is_lfs_pointer(csv_path):
        raise SystemExit(
            f"ERROR: {csv_path} looks like a Git-LFS pointer, not real data.\n"
            "Run 'git lfs pull' and retry. Load aborted."
        )

    print(f"Reading {csv_path} …", flush=True)
    rows, duplicates = _read_and_deduplicate(csv_path)
    total = len(rows)

    if duplicates:
        print(f"  {duplicates} duplicate row(s) removed (natural-key deduplication).")
    print(f"  {total} unique beer(s) to load.", flush=True)

    params_list = [_build_params(row) for row in rows]

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Count existing rows before upsert to derive insert/update split.
            cur.execute("SELECT COUNT(*) FROM beers")
            row_count = cur.fetchone()
            before: int = row_count[0] if row_count else 0

            cur.executemany(_UPSERT_SQL, params_list)

            cur.execute("SELECT COUNT(*) FROM beers")
            row_count = cur.fetchone()
            after: int = row_count[0] if row_count else 0

            inserted = after - before
            updated = total - inserted

            # Record provenance in dataset_meta (idempotent upsert).
            now_iso = datetime.now(timezone.utc).isoformat()
            for key, value in {
                "source_url":       _SOURCE_URL,
                "license":          _LICENSE,
                "snapshot_version": _SNAPSHOT_VERSION,
                "load_timestamp":   now_iso,
                "row_count":        str(total),
            }.items():
                cur.execute(
                    "INSERT INTO dataset_meta (key, value) VALUES (%s, %s)"
                    " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    (key, value),
                )

    print(
        f"Loaded {total} beer(s) (inserted={inserted} updated={updated}).",
        flush=True,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load beer dataset into PostgreSQL.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=_DEFAULT_CSV,
        metavar="PATH",
        help=f"Path to dataset CSV (default: {_DEFAULT_CSV})",
    )
    args = parser.parse_args()
    load(args.csv)

