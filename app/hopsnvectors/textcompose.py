"""Compose the `info` embedding-source text for a beer row and compute its hash."""
from __future__ import annotations

import hashlib

# Maps a taste attribute to a natural-language adjective used when that
# attribute is the dominant characteristic of the beer (highest score).
# Attributes absent from this map are not promoted to adjectives.
_TASTE_ADJECTIVES: dict[str, str] = {
    "bitter":      "bitter",
    "sweet":       "sweet",
    "sour":        "sour",
    "salty":       "salty",
    "hoppy":       "hoppy",
    "malty":       "malty",
    "fruits":      "fruity",
    "spices":      "spiced",
    "alcohol":     "strong",
    "body":        "full-bodied",
    "astringency": "astringent",
}

# Attributes that contribute to the natural-language taste summary.
# Listed in order of semantic importance for the embedding.
_TASTE_KEYS: list[str] = [
    "hoppy", "bitter", "malty", "sweet", "sour", "fruits",
    "spices", "salty", "alcohol", "body", "astringency",
]

# Minimum score for an attribute to be considered "prominent".
_TASTE_THRESHOLD = 40


def _taste_summary(taste: dict[str, int | None]) -> str:
    """Return a short natural-language phrase for dominant taste attributes.

    Only attributes with a score above the threshold are included.  Returns
    an empty string when no attribute clears the threshold.
    """
    adjectives = [
        _TASTE_ADJECTIVES[k]
        for k in _TASTE_KEYS
        if (taste.get(k) or 0) >= _TASTE_THRESHOLD and k in _TASTE_ADJECTIVES
    ]
    if not adjectives:
        return ""
    return "Taste: " + ", ".join(adjectives) + "."


def compose_info(
    beer_name: str,
    style: str | None = None,
    description: str | None = None,
    taste: dict[str, int | None] | None = None,
) -> str:
    """Build the descriptive text used as the embedding source.

    Combines name, style, description/notes, and dominant taste adjectives
    into human-readable prose.  Raw numeric scores are intentionally excluded
    — they are noise to the embedding model.  Empty or None inputs are
    silently skipped so that sparse rows still produce valid text.  Returns
    an empty string only when *all* inputs are absent or empty.
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

    summary = _taste_summary(taste)
    if summary:
        parts.append(summary)

    return " ".join(parts)


def text_hash(info: str) -> str:
    """Return the hex-encoded SHA-256 digest of *info* (UTF-8 encoded)."""
    return hashlib.sha256(info.encode()).hexdigest()

