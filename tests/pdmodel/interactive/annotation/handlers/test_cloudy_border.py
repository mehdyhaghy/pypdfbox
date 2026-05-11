"""Tests for the lite-port :class:`CloudyBorder` shim.

Upstream's CloudyBorder is a 1100-line geometry engine; the lite port
keeps the public surface (constructor + three ``create_cloudy_*``
methods + the ``get_*`` accessors) so callers in
``PDSquareAppearanceHandler`` / ``PDCircleAppearanceHandler`` /
``PDPolygonAppearanceHandler`` continue to type-check. Full path
generation is deferred — see the ``TODO: full path generation``
comments. These tests pin the API shape and the bbox seeding behaviour.
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
    # bbox unchanged because path generation is stubbed.
    assert cb.get_rectangle().get_width() == 100.0


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
    assert bbox.get_lower_left_x() == 1.0
    assert bbox.get_upper_right_y() == 9.0
