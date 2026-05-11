"""Tests for ``pypdfbox.examples.rendering.custom_graphics_stream_engine``."""
from __future__ import annotations

import pytest

from pypdfbox.contentstream.pdf_graphics_stream_engine import (
    PDFGraphicsStreamEngine,
)
from pypdfbox.examples.rendering.custom_graphics_stream_engine import (
    CustomGraphicsStreamEngine,
)


def test_subclasses_pdf_graphics_stream_engine() -> None:
    assert issubclass(CustomGraphicsStreamEngine, PDFGraphicsStreamEngine)


def test_can_construct_without_page() -> None:
    # The Java constructor is protected; in Python we still allow no-page
    # construction for tests by relying on the base default.
    engine = CustomGraphicsStreamEngine.__new__(CustomGraphicsStreamEngine)
    PDFGraphicsStreamEngine.__init__(engine, None)
    assert isinstance(engine, CustomGraphicsStreamEngine)


def test_print_helpers_use_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    engine = CustomGraphicsStreamEngine.__new__(CustomGraphicsStreamEngine)
    PDFGraphicsStreamEngine.__init__(engine, None)
    engine.move_to(1.5, 2.0)
    engine.line_to(3.0, 4.0)
    engine.curve_to(0.0, 0.0, 0.5, 0.5, 1.0, 1.0)
    engine.append_rectangle((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    engine.draw_image(object())
    engine.clip(0)
    engine.close_path()
    engine.end_path()
    engine.stroke_path()
    engine.fill_path(0)
    engine.fill_and_stroke_path(0)
    out = capsys.readouterr().out
    assert "moveTo 1.50 2.00" in out
    assert "lineTo 3.00 4.00" in out
    assert "curveTo 0.00 0.00, 0.50 0.50, 1.00 1.00" in out
    assert "appendRectangle 0.00 0.00, 1.00 0.00, 1.00 1.00, 0.00 1.00" in out
    assert "drawImage" in out
    assert "clip" in out
    assert "closePath" in out
    assert "endPath" in out
    assert "strokePath" in out
    assert "fillPath" in out
    assert "fillAndStrokePath" in out


def test_current_point_returns_origin() -> None:
    engine = CustomGraphicsStreamEngine.__new__(CustomGraphicsStreamEngine)
    PDFGraphicsStreamEngine.__init__(engine, None)
    assert engine.get_current_point() == (0.0, 0.0)
