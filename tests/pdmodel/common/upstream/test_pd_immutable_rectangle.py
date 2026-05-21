"""Ported from upstream PDFBox 3.0
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/PDImmutableRectangleTest.java``.

Verifies that the predefined paper-size constants on :class:`PDRectangle`
(``A0``..``A6``, ``LEGAL``, ``LETTER``) are :class:`PDImmutableRectangle`
instances and that the four coordinate setters raise on attempted
mutation.

Upstream raises Java ``UnsupportedOperationException``; pypdfbox raises
Python ``TypeError`` (the closest builtin) — see
``pypdfbox.pdmodel.common.pd_immutable_rectangle.PDImmutableRectangle``.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.pd_immutable_rectangle import PDImmutableRectangle
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


@pytest.fixture
def rect() -> PDRectangle:
    """``private PDRectangle rect = PDRectangle.A4;`` (Java line 28)."""
    return PDRectangle.A4  # type: ignore[attr-defined]


def test_class(rect: PDRectangle) -> None:
    """Mirrors upstream ``testClass`` (Java lines 38-50)."""
    assert isinstance(rect, PDImmutableRectangle)
    assert isinstance(PDRectangle.A0, PDImmutableRectangle)  # type: ignore[attr-defined]
    assert isinstance(PDRectangle.A1, PDImmutableRectangle)  # type: ignore[attr-defined]
    assert isinstance(PDRectangle.A2, PDImmutableRectangle)  # type: ignore[attr-defined]
    assert isinstance(PDRectangle.A3, PDImmutableRectangle)  # type: ignore[attr-defined]
    assert isinstance(PDRectangle.A4, PDImmutableRectangle)  # type: ignore[attr-defined]
    assert isinstance(PDRectangle.A5, PDImmutableRectangle)  # type: ignore[attr-defined]
    assert isinstance(PDRectangle.A6, PDImmutableRectangle)  # type: ignore[attr-defined]
    assert isinstance(PDRectangle.LEGAL, PDImmutableRectangle)  # type: ignore[attr-defined]
    assert isinstance(PDRectangle.LETTER, PDImmutableRectangle)  # type: ignore[attr-defined]


def test_set_upper_right_y(rect: PDRectangle) -> None:
    """Mirrors upstream ``testSetUpperRightY`` (Java lines 56-59).

    Upstream: ``UnsupportedOperationException``; pypdfbox: ``TypeError``.
    """
    with pytest.raises(TypeError):
        rect.set_upper_right_y(0)


def test_set_upper_right_x(rect: PDRectangle) -> None:
    """Mirrors upstream ``testSetUpperRightX`` (Java lines 65-68)."""
    with pytest.raises(TypeError):
        rect.set_upper_right_x(0)


def test_set_lower_left_y(rect: PDRectangle) -> None:
    """Mirrors upstream ``testSetLowerLeftY`` (Java lines 74-77)."""
    with pytest.raises(TypeError):
        rect.set_lower_left_y(0)


def test_set_lower_left_x(rect: PDRectangle) -> None:
    """Mirrors upstream ``testSetLowerLeftX`` (Java lines 83-86)."""
    with pytest.raises(TypeError):
        rect.set_lower_left_x(0)
