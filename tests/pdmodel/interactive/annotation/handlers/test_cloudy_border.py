"""Tests for the :class:`CloudyBorder` geometry engine ported from
``org.apache.pdfbox.pdmodel.interactive.annotation.handlers.CloudyBorder``.

These tests pin the public API + accessor behaviour and exercise the
three ``create_cloudy_*`` entry points end-to-end so the path generation
math is covered.
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.interactive.annotation.handlers.cloudy_border import (
    CloudyBorder,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _stream() -> PDAppearanceContentStream:
    return PDAppearanceContentStream(PDAppearanceStream(COSStream()))


def test_cloudy_border_constructor_records_arguments() -> None:
    rect = PDRectangle(10.0, 20.0, 110.0, 220.0)
    cb = CloudyBorder(_stream(), 2.0, 1.5, rect)
    # Seeded bbox tracks the input rectangle so callers that read
    # get_rectangle() before path generation see a sensible value.
    out = cb.get_rectangle()
    assert out.get_lower_left_x() == 10.0
    assert out.get_lower_left_y() == 20.0
    assert out.get_upper_right_x() == 110.0
    assert out.get_upper_right_y() == 220.0


def test_cloudy_border_get_matrix_returns_translation_to_bbox_origin() -> None:
    rect = PDRectangle(5.0, 7.0, 15.0, 17.0)
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    matrix = cb.get_matrix()
    assert matrix == [1.0, 0.0, 0.0, 1.0, -5.0, -7.0]


def test_cloudy_border_get_bbox_alias_returns_rectangle() -> None:
    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    assert (
        cb.get_bbox().get_upper_right_x() == cb.get_rectangle().get_upper_right_x()
    )


def test_cloudy_border_create_cloudy_rectangle_accepts_none_rd() -> None:
    rect = PDRectangle(0.0, 0.0, 100.0, 50.0)
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    cb.create_cloudy_rectangle(None)  # must not raise
    # Path generation produces a bbox that contains the input rectangle
    # (with curl tails extending slightly outside the perimeter).
    bbox = cb.get_rectangle()
    assert bbox.get_width() > 0.0
    assert bbox.get_height() > 0.0


def test_cloudy_border_get_rect_difference_with_null_annotation_rect() -> None:
    cb = CloudyBorder(_stream(), 2.0, 1.5, None)
    rd = cb.get_rect_difference()
    assert rd.get_lower_left_x() == 0.75
    assert rd.get_width() == 1.5


def test_cloudy_border_create_cloudy_polygon_updates_bbox() -> None:
    rect = PDRectangle(0.0, 0.0, 10.0, 10.0)
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    cb.create_cloudy_polygon([[1.0, 1.0], [9.0, 1.0], [9.0, 9.0]])
    bbox = cb.get_rectangle()
    # Path generation produces a bbox extending around the polygon
    # vertices (curls extend outside the polygon perimeter).
    assert bbox.get_width() > 0.0
    assert bbox.get_height() > 0.0


def test_cloudy_border_create_cloudy_ellipse_emits_path() -> None:
    rect = PDRectangle(0.0, 0.0, 60.0, 40.0)
    cb = CloudyBorder(_stream(), 2.0, 1.0, rect)
    cb.create_cloudy_ellipse(None)
    bbox = cb.get_rectangle()
    assert bbox.get_width() > 0.0
    assert bbox.get_height() > 0.0


def test_cloudy_border_arc_segment_emits_curve_to_stream() -> None:
    rect = PDRectangle(0.0, 0.0, 10.0, 10.0)
    cb = CloudyBorder(_stream(), 1.0, 1.0, rect)
    out: list[tuple[float, float]] = []
    cb.get_arc_segment(0.0, 1.0, 0.0, 0.0, 5.0, 5.0, out, True)
    # 1 move (start) + 3 control / endpoints for the curve.
    assert len(out) == 4


def test_cloudy_border_flatten_ellipse_returns_polygon() -> None:
    points = CloudyBorder.flatten_ellipse(0.0, 0.0, 50.0, 30.0)
    assert len(points) >= 8
    # First / last should approximately coincide because flatten_ellipse
    # closes the polygon.
    first = points[0]
    last = points[-1]
    assert abs(first[0] - last[0]) < 1.0
    assert abs(first[1] - last[1]) < 1.0


def test_cloudy_border_polygon_direction_is_signed() -> None:
    rect = PDRectangle(0.0, 0.0, 10.0, 10.0)
    cb = CloudyBorder(_stream(), 1.0, 1.0, rect)
    ccw = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    cw = list(reversed(ccw))
    assert cb.get_polygon_direction(ccw) > 0
    assert cb.get_polygon_direction(cw) < 0


def test_cloudy_border_compute_params_polygon_returns_negative_for_zero_length() -> None:
    rect = PDRectangle(0.0, 0.0, 10.0, 10.0)
    cb = CloudyBorder(_stream(), 1.0, 1.0, rect)
    array = [0.0, 0.0]
    assert cb.compute_params_polygon(1.0, 0.5, 0.829, 5.0, 0.0, array) == -1
