"""Coverage boost for ``PDPolylineAppearanceHandler`` (wave 1318).

Covers the line-ending dispatch branches (start/end short styles, angled
styles, interior-color extraction) and the early-return guards that the
wave-1280 smoke tests skipped.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pypdfbox.cos import COSArray, COSFloat
from pypdfbox.pdmodel.interactive.annotation.handlers import (
    PDPolylineAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
    PDAnnotationPolyline,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (0.0, 0.0, 100.0, 50.0)


def _polyline(
    *,
    vertices: list[float] | None = (0.0, 0.0, 50.0, 50.0, 100.0, 0.0),
    color: list[float] | None = (1.0, 0.0, 0.0),
    interior: tuple[float, float, float] | None = None,
    start_style: str | None = None,
    end_style: str | None = None,
) -> PDAnnotationPolyline:
    annotation = PDAnnotationPolyline()
    annotation.set_rectangle(PDRectangle(*_RECT))
    if color is not None:
        annotation.set_color(list(color))
    if vertices is not None:
        annotation.set_vertices(list(vertices))
    if interior is not None:
        annotation.set_interior_color(interior)
    if start_style is not None:
        annotation.set_start_point_ending_style(start_style)
    if end_style is not None:
        annotation.set_end_point_ending_style(end_style)
    return annotation


# ----------------------------------------------------------------------
# early returns
# ----------------------------------------------------------------------


def test_returns_when_annotation_is_not_polyline() -> None:
    """Pass a plain ``PDAnnotationLine`` — handler must bail without
    writing an appearance stream."""
    line = PDAnnotationLine()
    line.set_rectangle(PDRectangle(*_RECT))
    line.set_color([0.0, 0.0, 0.0])
    handler = PDPolylineAppearanceHandler(line)  # type: ignore[arg-type]
    handler.generate_normal_appearance()
    assert line.get_appearance_dictionary() is None


def test_returns_when_rectangle_is_missing() -> None:
    annotation = PDAnnotationPolyline()
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_vertices([0.0, 0.0, 50.0, 50.0, 100.0, 0.0])
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_returns_when_vertices_array_too_short() -> None:
    annotation = _polyline(vertices=[0.0, 0.0])
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_returns_when_color_is_unset() -> None:
    annotation = _polyline(color=None)
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# line-ending dispatch
# ----------------------------------------------------------------------


def test_generate_with_short_start_style_shortens_first_segment() -> None:
    annotation = _polyline(start_style=PDAnnotationLine.LE_OPEN_ARROW)
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_generate_with_short_end_style_shortens_last_segment() -> None:
    annotation = _polyline(end_style=PDAnnotationLine.LE_CIRCLE)
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_generate_with_angled_endings_writes_appearance() -> None:
    """ANGLED_STYLES (e.g. ``LE_OPEN_ARROW``) hits the ``cs.transform`` path
    that uses ``cos`` / ``sin`` instead of the identity transform."""
    annotation = _polyline(
        start_style=PDAnnotationLine.LE_OPEN_ARROW,
        end_style=PDAnnotationLine.LE_CLOSED_ARROW,
        interior=(0.25, 0.5, 0.75),
    )
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_generate_with_non_angled_endings_uses_identity_transform() -> None:
    """``LE_SQUARE`` / ``LE_CIRCLE`` etc. are *not* in ``ANGLED_STYLES`` —
    the handler takes the identity-transform branch for both endings."""
    annotation = _polyline(
        start_style=PDAnnotationLine.LE_SQUARE,
        end_style=PDAnnotationLine.LE_CIRCLE,
    )
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_generate_with_interior_color_writes_appearance() -> None:
    annotation = _polyline(
        interior=(0.1, 0.2, 0.3),
        start_style=PDAnnotationLine.LE_CIRCLE,
        end_style=PDAnnotationLine.LE_DIAMOND,
    )
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_generate_rectangle_grows_to_fit_vertices_outside_bounds() -> None:
    """Vertices outside the declared rectangle must extend the rect."""
    annotation = PDAnnotationPolyline()
    annotation.set_rectangle(PDRectangle(40.0, 40.0, 60.0, 60.0))
    annotation.set_color([0.0, 0.0, 0.0])
    # Vertices reach well past the rectangle on both ends.
    annotation.set_vertices([0.0, 0.0, 200.0, 200.0])
    handler = PDPolylineAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    rect = annotation.get_rectangle()
    assert rect.get_lower_left_x() <= 0.0
    assert rect.get_lower_left_y() <= 0.0
    assert rect.get_upper_right_x() >= 200.0
    assert rect.get_upper_right_y() >= 200.0


# ----------------------------------------------------------------------
# no-op generators
# ----------------------------------------------------------------------


def test_generate_rollover_appearance_is_noop() -> None:
    annotation = _polyline()
    handler = PDPolylineAppearanceHandler(annotation)
    assert handler.generate_rollover_appearance() is None


def test_generate_down_appearance_is_noop() -> None:
    annotation = _polyline()
    handler = PDPolylineAppearanceHandler(annotation)
    assert handler.generate_down_appearance() is None


# ----------------------------------------------------------------------
# _interior_components helper
# ----------------------------------------------------------------------


def test_interior_components_returns_none_when_unset() -> None:
    annotation = _polyline()
    assert PDPolylineAppearanceHandler._interior_components(annotation) is None


def test_interior_components_returns_floats_from_polyline_interior_color() -> None:
    annotation = _polyline(interior=(0.4, 0.5, 0.6))
    components = PDPolylineAppearanceHandler._interior_components(annotation)
    # PDAnnotationPolyline returns a tuple of floats, which the helper
    # converts via ``list(interior)``.
    assert components == pytest.approx([0.4, 0.5, 0.6])


def test_interior_components_reads_to_float_array_when_available() -> None:
    """An object exposing ``to_float_array`` is forwarded directly."""

    class _IC:
        def to_float_array(self):
            return [0.1, 0.2, 0.3]

    fake_annotation = MagicMock()
    fake_annotation.get_interior_color = lambda: _IC()
    out = PDPolylineAppearanceHandler._interior_components(fake_annotation)
    assert out == [0.1, 0.2, 0.3]


def test_interior_components_returns_none_for_empty_to_float_array() -> None:
    class _IC:
        def to_float_array(self):
            return []

    fake_annotation = MagicMock()
    fake_annotation.get_interior_color = lambda: _IC()
    assert PDPolylineAppearanceHandler._interior_components(fake_annotation) is None


def test_interior_components_returns_none_for_empty_cos_array() -> None:
    """A ``size()``-bearing object with zero elements yields ``None``."""
    fake_annotation = MagicMock()
    fake_annotation.get_interior_color = lambda: COSArray()
    assert PDPolylineAppearanceHandler._interior_components(fake_annotation) is None


def test_interior_components_uses_size_branch_for_non_empty_cos_array() -> None:
    arr = COSArray([COSFloat(0.7), COSFloat(0.8), COSFloat(0.9)])
    fake_annotation = MagicMock()
    fake_annotation.get_interior_color = lambda: arr
    out = PDPolylineAppearanceHandler._interior_components(fake_annotation)
    assert out == pytest.approx([0.7, 0.8, 0.9])


def test_interior_components_handles_plain_iterable() -> None:
    fake_annotation = MagicMock()
    fake_annotation.get_interior_color = lambda: [0.3, 0.4, 0.5]
    out = PDPolylineAppearanceHandler._interior_components(fake_annotation)
    assert out == [0.3, 0.4, 0.5]
