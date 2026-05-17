"""Smoke + coverage tests for :class:`DrawPrintTextLocations`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.examples.util.draw_print_text_locations import DrawPrintTextLocations
from pypdfbox.pdmodel.pd_document import PDDocument

# ---------------------------------------------------------------------------
# Existing smoke-level coverage
# ---------------------------------------------------------------------------


def test_run_blank_pdf(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("draw.pdf")
    DrawPrintTextLocations.run(str(src))


# ---------------------------------------------------------------------------
# main() / usage()
# ---------------------------------------------------------------------------


def test_usage_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    DrawPrintTextLocations.usage()
    err = capsys.readouterr().err
    assert "DrawPrintTextLocations" in err


def test_main_no_args_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    DrawPrintTextLocations.main(None)
    err = capsys.readouterr().err
    assert "DrawPrintTextLocations" in err


def test_main_too_many_args_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    DrawPrintTextLocations.main(["one.pdf", "two.pdf"])
    err = capsys.readouterr().err
    assert "DrawPrintTextLocations" in err


def test_main_single_arg_invokes_run(
    make_pdf: Callable[..., Path],
) -> None:
    src = make_pdf("draw-main.pdf")
    DrawPrintTextLocations.main([str(src)])


# ---------------------------------------------------------------------------
# show_glyph() / calculate_glyph_bounds()
# ---------------------------------------------------------------------------


def test_show_glyph_suppresses_attribute_error(
    make_pdf: Callable[..., Path],
) -> None:
    """If the base ``show_glyph`` isn't implemented we still must not raise."""
    src = make_pdf("glyph.pdf")
    with PDDocument.load(str(src)) as doc:
        stripper = DrawPrintTextLocations(doc, str(src))
        # ``Any``-typed args — show_glyph swallows AttributeError raised
        # by the missing base implementation.
        stripper.show_glyph(None, None, 0, None)


def test_calculate_glyph_bounds_returns_none(
    make_pdf: Callable[..., Path],
) -> None:
    src = make_pdf("bounds.pdf")
    with PDDocument.load(str(src)) as doc:
        stripper = DrawPrintTextLocations(doc, str(src))
        assert stripper.calculate_glyph_bounds(None, None, 0) is None


# ---------------------------------------------------------------------------
# write_string() — exercise both the font-name happy path and the fallback
# ---------------------------------------------------------------------------


class _FakeFont:
    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


class _FakeText:
    """Subset of upstream's ``TextPosition`` good enough for write_string."""

    def __init__(self, font: object, unicode_value: str) -> None:
        self._font = font
        self._unicode = unicode_value

    def get_font(self) -> object:
        return self._font

    def get_x_dir_adj(self) -> float:
        return 1.0

    def get_y_dir_adj(self) -> float:
        return 2.0

    def get_font_size(self) -> float:
        return 12.0

    def get_x_scale(self) -> float:
        return 1.0

    def get_height_dir(self) -> float:
        return 10.0

    def get_width_of_space(self) -> float:
        return 3.0

    def get_width_dir_adj(self) -> float:
        return 4.0

    def get_unicode(self) -> str:
        return self._unicode


def _make_stripper(
    make_pdf: Callable[..., Path], name: str
) -> DrawPrintTextLocations:
    src = make_pdf(name)
    doc = PDDocument.load(str(src))
    return DrawPrintTextLocations(doc, str(src))


def test_write_string_emits_per_glyph_line(
    make_pdf: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    stripper = _make_stripper(make_pdf, "wstr.pdf")
    try:
        text = _FakeText(_FakeFont("Helvetica"), "A")
        stripper.write_string("A", [text])
    finally:
        stripper.document.close()
    out = capsys.readouterr().out
    assert "String[" in out
    assert "font=Helvetica:12.0" in out


def test_write_string_falls_back_when_font_raises(
    make_pdf: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _BadText(_FakeText):
        def get_font(self):  # type: ignore[override]
            raise RuntimeError("no font")

    stripper = _make_stripper(make_pdf, "wstr-bad.pdf")
    try:
        text = _BadText(None, "B")
        stripper.write_string("B", [text])
    finally:
        stripper.document.close()
    out = capsys.readouterr().out
    assert "font=<unknown>" in out


def test_class_scale_constant() -> None:
    assert DrawPrintTextLocations.SCALE == 4
