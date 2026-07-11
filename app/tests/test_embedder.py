"""Unit tests for hopsnvectors.embedder (no DB, model is mocked/absent)."""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


def test_load_model_failure_raises_system_exit():
    """_load_model() must raise SystemExit with a helpful message when the model
    cannot be loaded (edge case 10 — cold cache with no network access)."""
    from hopsnvectors import embedder

    with patch.dict(sys.modules, {"sentence_transformers": None}):
        with pytest.raises(SystemExit, match="Could not load model"):
            embedder._load_model()
