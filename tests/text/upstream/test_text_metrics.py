"""
No dedicated upstream test class exists for ``TextMetrics`` in
Apache PDFBox 3.0:

  - There is no ``pdfbox/src/main/java/org/apache/pdfbox/text/TextMetrics.java``
    and consequently no ``TestTextMetrics.java`` upstream.

The data-holder shape is described in pypdfbox's task spec and exposed
publicly as :class:`pypdfbox.text.TextMetrics`. The tests below assert
that the conceptual contract (constructed from a ``TextPosition``;
exposes ascent / descent / height / x / y; ascent and descent are
mutable) holds — i.e. the same surface that PDFBox-style downstream
callers would expect.
"""

from __future__ import annotations

import pytest

from pypdfbox.text import TextMetrics, TextPosition


def test_construct_from_text_position() -> None:
    tp = TextPosition(text="A", x=5.0, y=7.0, font_size=10.0)
    metrics = TextMetrics(tp)
    assert metrics.get_x() == 5.0
    assert metrics.get_y() == 7.0
    # height is non-zero for a non-zero font size
    assert metrics.get_height() > 0


def test_height_equals_ascent_plus_abs_descent() -> None:
    tp = TextPosition(text="A", x=0.0, y=0.0, font_size=20.0)
    metrics = TextMetrics(tp)
    assert metrics.get_height() == pytest.approx(
        metrics.get_ascent() + abs(metrics.get_descent())
    )


def test_ascent_descent_are_mutable() -> None:
    tp = TextPosition(text="A", x=0.0, y=0.0, font_size=10.0)
    metrics = TextMetrics(tp)
    metrics.set_ascent(11.5)
    metrics.set_descent(-3.25)
    assert metrics.get_ascent() == 11.5
    assert metrics.get_descent() == -3.25
    assert metrics.get_height() == pytest.approx(14.75)
