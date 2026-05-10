from __future__ import annotations

from pypdfbox.cos import COSNull


def test_to_string_returns_upstream_literal() -> None:
    """``COSNull.toString()`` upstream returns the literal ``"COSNull{}"``."""
    assert COSNull.NULL.to_string() == "COSNull{}"


def test_to_string_is_stable_across_calls() -> None:
    """Singleton invariant: the literal never changes between calls."""
    assert COSNull.NULL.to_string() == COSNull.NULL.to_string()
