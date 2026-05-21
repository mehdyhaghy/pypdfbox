"""Upstream-equivalent parity tests for the
``pypdfbox.text.TextMetrics`` ratio constants and edge cases.

Upstream baseline: PDFBox 3.0.x — there is no upstream class file for
``TextMetrics`` (the data holder is a private helper in the
``PDFTextStripper`` codebase), but the lite port in
``pypdfbox.text.text_metrics`` exposes the upstream-style accessors
(``get_ascent`` / ``get_descent`` / ``get_height``) and the 0.7 /-0.2
font-size ratios PDFBox uses to derive cap-height and descender from
the font size when no font descriptor is available.

The existing ``test_text_metrics.py`` covers the round-trip; this
parity file pins the ratio constants directly so a refactor that
silently moves to a 0.8 / -0.1 split (a common "for accessibility"
mistake) is caught.
"""
from __future__ import annotations

import pytest

from pypdfbox.text import TextMetrics, TextPosition


def _metrics(font_size: float) -> TextMetrics:
    tp = TextPosition(text="A", x=0.0, y=0.0, font_size=font_size)
    return TextMetrics(tp)


@pytest.mark.parametrize(
    "font_size, expected_ascent",
    [
        (10.0, 7.0),
        (12.0, 8.4),
        (20.0, 14.0),
        (1.0, 0.7),
        (0.0, 0.0),
    ],
)
def test_ascent_is_seven_tenths_of_font_size(
    font_size: float, expected_ascent: float
) -> None:
    """Upstream's cap-height approximation: ``ascent = 0.7 * fontSize``.
    Pin so the constant doesn't drift.
    """
    assert _metrics(font_size).get_ascent() == pytest.approx(expected_ascent)


@pytest.mark.parametrize(
    "font_size, expected_descent",
    [
        (10.0, -2.0),
        (12.0, -2.4),
        (20.0, -4.0),
        (1.0, -0.2),
        (0.0, 0.0),
    ],
)
def test_descent_is_negative_two_tenths_of_font_size(
    font_size: float, expected_descent: float
) -> None:
    """Upstream's descender approximation: ``descent = -0.2 * fontSize``
    (returned negative). Pin the sign and the constant.
    """
    assert _metrics(font_size).get_descent() == pytest.approx(expected_descent)


def test_descent_is_strictly_non_positive_for_non_negative_font_sizes() -> None:
    """The descender ratio is signed; positive font sizes must yield
    non-positive descent values."""
    for fs in [0.0, 1.0, 12.0, 100.0]:
        assert _metrics(fs).get_descent() <= 0.0


@pytest.mark.parametrize("font_size", [10.0, 12.0, 18.0])
def test_height_is_nine_tenths_of_font_size(font_size: float) -> None:
    """Total line height = ascent + |descent| = 0.7 + 0.2 = 0.9 *
    fontSize. Pin the ratio so the parts don't drift independently.
    """
    expected = 0.9 * font_size
    assert _metrics(font_size).get_height() == pytest.approx(expected)


def test_zero_font_size_yields_zero_metrics() -> None:
    """A zero font size collapses every metric to 0 — pin to avoid a
    NaN regression."""
    m = _metrics(0.0)
    assert m.get_ascent() == 0.0
    assert m.get_descent() == 0.0
    assert m.get_height() == 0.0


def test_ratio_constants_exposed_for_subclass_overrides() -> None:
    """The 0.7 / -0.2 ratios are class-level constants so subclasses
    can override them (e.g. to apply a font-descriptor-derived cap
    height). Pin the names and values.
    """
    assert TextMetrics._ASCENT_RATIO == 0.7
    assert TextMetrics._DESCENT_RATIO == -0.2


def test_set_ascent_does_not_modify_descent() -> None:
    """Mutator independence: ``set_ascent`` only touches ascent."""
    m = _metrics(10.0)
    original_descent = m.get_descent()
    m.set_ascent(99.0)
    assert m.get_descent() == original_descent


def test_set_descent_does_not_modify_ascent() -> None:
    m = _metrics(10.0)
    original_ascent = m.get_ascent()
    m.set_descent(-50.0)
    assert m.get_ascent() == original_ascent


def test_set_ascent_propagates_to_height() -> None:
    """``get_height`` is derived from the current ascent + |descent|
    rather than cached at construction."""
    m = _metrics(10.0)
    m.set_ascent(100.0)
    assert m.get_height() == pytest.approx(100.0 + abs(m.get_descent()))


def test_set_descent_with_positive_value_still_contributes_magnitude() -> None:
    """``get_height`` uses ``abs(descent)``, so setting a positive
    descent must still contribute to the height (just like a negative
    one would)."""
    m = _metrics(10.0)
    m.set_descent(5.0)  # positive, unusual
    assert m.get_height() == pytest.approx(m.get_ascent() + 5.0)
