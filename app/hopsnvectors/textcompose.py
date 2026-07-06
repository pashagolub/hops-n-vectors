"""Compose the `info` embedding-source text for a beer row and compute its hash."""
from __future__ import annotations

import hashlib


# Taste attribute column names (as stored in DB) and their display labels.
_TASTE_LABELS: list[tuple[str, str]] = [
    ("astringency", "Astringency"),
    ("body", "Body"),
    ("alcohol", "Alcohol"),
    ("bitter", "Bitter"),
    ("sweet", "Sweet"),
    ("sour", "Sour"),
    ("salty", "Salty"),
    ("fruits", "Fruits"),
    ("hoppy", "Hoppy"),
    ("spices", "Spices"),
    ("malty", "Malty"),
]


def compose_info(
    beer_name: str,
    style: str | None = None,
    description: str | None = None,
    taste: dict[str, int | None] | None = None,
) -> str:
    """Build the descriptive text used as the embedding source.

    Combines name, style, description/notes, and non-zero taste attributes
    into human-readable prose.  Empty or None inputs are silently skipped so
    that sparse rows still produce valid text.  Returns an empty string only
    when *all* inputs are absent or empty.
    """
    parts: list[str] = []
    taste = taste or {}

    name = (beer_name or "").strip()
    if name:
        parts.append(name)

    sty = (style or "").strip()
    if sty:
        parts.append(f"Style: {sty}.")

    desc = (description or "").strip()
    if desc:
        parts.append(desc)

    taste_parts = [
        f"{label} {taste.get(key) or 0}"
        for key, label in _TASTE_LABELS
        if (taste.get(key) or 0) > 0
    ]
    if taste_parts:
        parts.append("Taste profile \u2014 " + ", ".join(taste_parts) + ".")

    return " ".join(parts)


def text_hash(info: str) -> str:
    """Return the hex-encoded SHA-256 digest of *info* (UTF-8 encoded)."""
    return hashlib.sha256(info.encode()).hexdigest()

