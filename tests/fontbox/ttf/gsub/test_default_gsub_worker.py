"""Tests for :class:`DefaultGsubWorker`.

Ported (in spirit) from ``DefaultGsubWorkerTest.java`` upstream — that
Java test asserts the result is an unmodifiable view of the argument.
Python lists have no unmodifiable wrapper, so we instead assert the
worker returns an equal list whose mutation does not affect the input.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import DefaultGsubWorker


def test_apply_transforms_returns_equal_sequence() -> None:
    sut = DefaultGsubWorker()
    original = [1, 2, 3, 4, 5]
    result = sut.apply_transforms(original)
    assert result == original


def test_apply_transforms_returns_defensive_copy() -> None:
    """Mutating the result must not corrupt the original list."""
    sut = DefaultGsubWorker()
    original = [1, 2, 3]
    result = sut.apply_transforms(original)
    result.clear()
    assert original == [1, 2, 3]


def test_apply_transforms_empty_input() -> None:
    sut = DefaultGsubWorker()
    assert sut.apply_transforms([]) == []


def test_apply_transforms_does_not_alias_input() -> None:
    sut = DefaultGsubWorker()
    original = [10, 20, 30]
    result = sut.apply_transforms(original)
    assert result is not original
