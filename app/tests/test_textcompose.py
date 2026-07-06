"""Unit tests for hopsnvectors.textcompose."""
import pytest

from hopsnvectors.textcompose import compose_info, text_hash


# ---------------------------------------------------------------------------
# compose_info
# ---------------------------------------------------------------------------

def test_compose_includes_name_style_description():
    info = compose_info("Stout Porter", style="Porter", description="Dark and roasty")
    assert "Stout Porter" in info
    assert "Porter" in info
    assert "Dark and roasty" in info


def test_compose_includes_nonzero_taste_attributes():
    info = compose_info("IPA", taste={"hoppy": 90, "bitter": 80})
    assert "Hoppy 90" in info
    assert "Bitter 80" in info


def test_compose_skips_zero_taste_attributes():
    info = compose_info("Lager", taste={"hoppy": 0, "bitter": 0, "sweet": None})
    assert "Taste profile" not in info


def test_compose_empty_description_is_skipped():
    info = compose_info("Pale Ale", style="American Pale Ale", description="")
    assert "Pale Ale" in info
    assert "American Pale Ale" in info
    # No trailing artefact from empty description.
    assert "  " not in info


def test_compose_none_fields_do_not_raise():
    info = compose_info("Beer", style=None, description=None)
    assert "Beer" in info


def test_compose_all_empty_returns_empty_string():
    info = compose_info("", style=None, description=None, taste={})
    assert info == ""


def test_compose_non_ascii_name():
    """Non-ASCII beer names must round-trip without error (edge case 3)."""
    info = compose_info("K\u00f6stritzer Schwarzbier", style="Schwarzbier")
    assert "K\u00f6stritzer" in info


def test_compose_taste_profile_label_present():
    info = compose_info("Stout", taste={"malty": 100})
    assert "Taste profile" in info


# ---------------------------------------------------------------------------
# text_hash
# ---------------------------------------------------------------------------

def test_hash_is_deterministic():
    assert text_hash("hello world") == text_hash("hello world")


def test_hash_differs_for_different_inputs():
    assert text_hash("beer one") != text_hash("beer two")


def test_hash_is_64_char_hex_string():
    h = text_hash("test")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_of_empty_string_is_stable():
    # sha256("") must not raise and must be deterministic.
    h = text_hash("")
    assert len(h) == 64

