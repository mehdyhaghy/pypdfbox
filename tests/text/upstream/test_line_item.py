"""Upstream-equivalent parity tests for ``pypdfbox.text.LineItem``.

Upstream baseline: PDFBox 3.0.x.
Source: ``pdfbox/src/main/java/org/apache/pdfbox/text/PDFTextStripper.java``
lines 2133-2163 (the package-private static inner class
``LineItem``).

Upstream's ``LineItem`` is a private static inner class with a single
constructor taking a nullable ``TextPosition`` and a class-level
``WORD_SEPARATOR`` singleton constructed with ``null``. Upstream has no
JUnit for the inner class — it's tested transitively through
``PDFTextStripper.writePage``. We pin the contract directly so a future
re-arrange of the ``WORD_SEPARATOR`` sentinel (or a switch to a Python
``None``-only convention) gets caught.
"""
from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.text import LineItem, TextPosition


def _make_text_position(text: str = "a") -> TextPosition:
    """Build a minimal :class:`TextPosition` for use as a non-separator
    payload. Mirrors the dataclass-style construction shape used in
    upstream-parity tests for ``PDFTextStripper``.
    """
    return TextPosition(
        text=text,
        x=0.0,
        y=0.0,
        font_size=12.0,
        width=10.0,
    )


def test_default_constructor_is_word_separator() -> None:
    """Upstream's no-arg constructor delegates to ``LineItem(null)``."""
    item = LineItem()
    assert item.is_word_separator() is True
    assert item.get_text_position() is None


def test_constructor_with_text_position_is_not_word_separator() -> None:
    tp = _make_text_position()
    item = LineItem(tp)
    assert item.is_word_separator() is False
    assert item.get_text_position() is tp


def test_word_separator_singleton_is_shared() -> None:
    """Upstream's ``WORD_SEPARATOR`` is ``static final``; every caller
    sees the same instance. Pin that contract so a refactor doesn't
    silently produce fresh instances per call.
    """
    a = LineItem.get_word_separator()
    b = LineItem.get_word_separator()
    assert a is b
    assert a is LineItem.WORD_SEPARATOR


def test_word_separator_singleton_is_a_word_separator() -> None:
    sep = LineItem.get_word_separator()
    assert sep.is_word_separator() is True
    assert sep.get_text_position() is None


def test_get_text_position_returns_constructor_argument() -> None:
    """Identity round-trip: the wrapped object must be the same instance
    handed to the constructor (no defensive copy)."""
    tp = _make_text_position("X")
    item = LineItem(tp)
    assert item.get_text_position() is tp


def test_word_separator_distinct_from_a_payload_item() -> None:
    """A LineItem built around a real ``TextPosition`` is not equal /
    identical to the sentinel. Pin so a future ``__eq__`` override
    can't collapse the two.
    """
    payload = LineItem(_make_text_position())
    sep = LineItem.get_word_separator()
    assert payload is not sep


@pytest.mark.parametrize(
    "kwarg, expected_is_sep",
    [
        ({}, True),
        ({"text_position": None}, True),
    ],
    ids=["no_arg", "explicit_none"],
)
def test_no_arg_and_explicit_none_both_produce_separators(
    kwarg: dict[str, Any], expected_is_sep: bool
) -> None:
    item = LineItem(**kwarg)
    assert item.is_word_separator() is expected_is_sep
