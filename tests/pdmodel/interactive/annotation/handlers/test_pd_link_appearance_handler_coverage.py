"""Coverage-boost tests for
``pypdfbox.pdmodel.interactive.annotation.handlers.pd_link_appearance_handler``.

Closes the remaining gaps:

* Early return when the wrong annotation type is passed
  (``generate_normal_appearance`` line 42).
* Early return when ``/Rect`` is missing (``rect is None`` branch).
* ``/QuadPoints`` outside of ``/Rect`` → warning + fall back to ``/Rect``
  (lines 67-80).
* Underlined link (``/BS /S /U``) — emits two moves + line per quad and
  skips the close_path block (line 98 branch).
* ``get_line_width`` branches: /BS width path, /Border-array via
  :class:`COSFloat` / :class:`COSInteger`, and the 1.0 default
  (lines 127, 133).
* ``_color_components_from_annotation`` returning None falls back to
  black ``[0.0]``.
* No-op rollover / down appearance hooks (returning ``None``).
"""

from __future__ import annotations

import logging

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_link_appearance_handler import (
    PDLinkAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (0.0, 0.0, 100.0, 50.0)


def _link_with_color() -> PDAnnotationLink:
    annotation = PDAnnotationLink()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    return annotation


def _appearance_bytes(annotation) -> bytes:
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    stream = ap.get_normal_appearance().get_appearance_stream()
    return stream.get_stream().to_byte_array()


# ----------------------------------------------------------------------
# generate_normal_appearance — early-return when wrong annotation type
# ----------------------------------------------------------------------


def test_generate_normal_appearance_returns_when_not_link() -> None:
    """Line 42: ``if not isinstance(annotation, PDAnnotationLink):
    return`` — pass a plain PDAnnotation."""
    annotation = PDAnnotation()
    annotation.set_rectangle(PDRectangle(*_RECT))
    handler = PDLinkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# generate_normal_appearance — /Rect missing early return
# ----------------------------------------------------------------------


def test_generate_normal_appearance_returns_when_rect_missing() -> None:
    """Line 47: when /Rect is None the handler bails before writing /AP."""
    annotation = PDAnnotationLink()
    annotation.set_color([0.0, 0.0, 0.0])
    # Do NOT set a rectangle.
    PDLinkAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# generate_normal_appearance — happy path with /Rect and no /QuadPoints
# ----------------------------------------------------------------------


def test_generate_normal_appearance_with_rect_only_emits_path() -> None:
    """No /QuadPoints → synthesise one from the (padded) rectangle and
    emit a closed quad. Verifies the rectangle-fallback branch."""
    annotation = _link_with_color()
    PDLinkAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # move_to + 3 line_to + close + stroke.
    assert b"m" in body
    assert b"l" in body
    assert b"h" in body
    assert b"S" in body


# ----------------------------------------------------------------------
# generate_normal_appearance — /QuadPoints inside /Rect (happy path)
# ----------------------------------------------------------------------


def test_generate_normal_appearance_with_quad_points_inside_rect() -> None:
    annotation = _link_with_color()
    # All quad points lie inside /Rect (0,0,100,50).
    annotation.set_quad_points(
        [10.0, 10.0, 90.0, 10.0, 90.0, 40.0, 10.0, 40.0]
    )
    PDLinkAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"m" in body
    assert b"l" in body
    assert b"h" in body


# ----------------------------------------------------------------------
# generate_normal_appearance — /QuadPoints outside /Rect → warn + fallback
# ----------------------------------------------------------------------


def test_generate_normal_appearance_with_quad_points_outside_rect_logs_warning(
    caplog,
) -> None:
    """Lines 67-80: at least one /QuadPoints coordinate outside /Rect →
    log a warning and fall back to the rectangle path."""
    annotation = _link_with_color()
    # x=200 is outside /Rect (right edge = 100).
    annotation.set_quad_points(
        [200.0, 10.0, 90.0, 10.0, 90.0, 40.0, 10.0, 40.0]
    )
    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.pdmodel.interactive.annotation.handlers.pd_link_appearance_handler",
    ):
        PDLinkAppearanceHandler(annotation).generate_normal_appearance()
    # Warning was emitted.
    messages = [r.message for r in caplog.records]
    assert any("QuadPoints" in m and "outside" in m for m in messages)
    # And the path is still emitted (rectangle fallback).
    body = _appearance_bytes(annotation)
    assert b"m" in body


# ----------------------------------------------------------------------
# generate_normal_appearance — underlined link (/BS /S /U)
# ----------------------------------------------------------------------


def test_generate_normal_appearance_underlined_skips_close_path() -> None:
    """Line 98 + the ``if not underlined:`` block: when /BS /S is /U we
    only emit one ``m`` + one ``l`` per quad (no second line_to / close).
    """
    annotation = _link_with_color()
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_UNDERLINE)
    annotation.set_border_style(bs)
    annotation.set_quad_points(
        [10.0, 10.0, 90.0, 10.0, 90.0, 40.0, 10.0, 40.0]
    )
    PDLinkAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Underline => one m + one l + stroke, no h (close path).
    assert b"m" in body
    assert b"l" in body
    # No close_path for underlines.
    assert b"\nh\n" not in body
    assert b" h\n" not in body


def test_generate_normal_appearance_solid_style_emits_close_path() -> None:
    """Negation of line 98: a non-underline border style keeps the
    close-path branch active."""
    annotation = _link_with_color()
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_SOLID)
    annotation.set_border_style(bs)
    annotation.set_quad_points(
        [10.0, 10.0, 90.0, 10.0, 90.0, 40.0, 10.0, 40.0]
    )
    PDLinkAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"h" in body


# ----------------------------------------------------------------------
# generate_normal_appearance — /C absent → black fallback [0.0]
# ----------------------------------------------------------------------


def test_generate_normal_appearance_color_none_falls_back_to_black() -> None:
    """Lines 52-53: stroke_components is None → ``[0.0]`` (DeviceGray
    black)."""
    annotation = PDAnnotationLink()
    annotation.set_rectangle(PDRectangle(*_RECT))
    # No set_color() — /C absent.
    PDLinkAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # DeviceGray stroking color (G) operator.
    assert b"G" in body or b"g" in body


# ----------------------------------------------------------------------
# get_line_width — /BS, /Border, default branches
# ----------------------------------------------------------------------


def test_get_line_width_uses_border_style_width() -> None:
    """Line 127: when /BS is set, return that width."""
    annotation = _link_with_color()
    bs = PDBorderStyleDictionary()
    bs.set_width(4.25)
    annotation.set_border_style(bs)
    assert PDLinkAppearanceHandler(annotation).get_line_width() == 4.25


def test_get_line_width_uses_border_array_float() -> None:
    """Line 132-133: /BS absent, /Border array length >= 3 with a
    :class:`COSFloat` at index 2."""
    annotation = _link_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSFloat(2.5))
    annotation.set_border(border)
    assert PDLinkAppearanceHandler(annotation).get_line_width() == 2.5


def test_get_line_width_uses_border_array_integer() -> None:
    annotation = _link_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(6))
    annotation.set_border(border)
    assert PDLinkAppearanceHandler(annotation).get_line_width() == 6.0


def test_get_line_width_default_when_border_third_element_unknown() -> None:
    """Line 133 explicitly: /BS absent, /Border third element is neither
    COSFloat nor COSInteger — must fall through to 1.0."""
    annotation = _link_with_color()
    border = COSArray()
    border.add(COSInteger.get(0))
    border.add(COSInteger.get(0))
    border.add(COSName.get_pdf_name("Solid"))
    annotation.set_border(border)
    assert PDLinkAppearanceHandler(annotation).get_line_width() == 1.0


def test_get_line_width_default_when_no_border() -> None:
    """The synthesised default /Border = [0 0 1] yields 1.0."""
    annotation = _link_with_color()
    assert PDLinkAppearanceHandler(annotation).get_line_width() == 1.0


# ----------------------------------------------------------------------
# rollover / down — no-op hooks
# ----------------------------------------------------------------------


def test_generate_rollover_appearance_is_noop() -> None:
    annotation = _link_with_color()
    handler = PDLinkAppearanceHandler(annotation)
    assert handler.generate_rollover_appearance() is None


def test_generate_down_appearance_is_noop() -> None:
    annotation = _link_with_color()
    handler = PDLinkAppearanceHandler(annotation)
    assert handler.generate_down_appearance() is None


# ----------------------------------------------------------------------
# constructor — single-arg vs document-arg overloads
# ----------------------------------------------------------------------


def test_constructor_with_document_argument() -> None:
    from pypdfbox.pdmodel.pd_document import PDDocument

    annotation = _link_with_color()
    document = PDDocument()
    handler = PDLinkAppearanceHandler(annotation, document)
    assert handler.get_annotation() is annotation
    assert handler.get_document() is document


def test_constructor_with_document_argument_none() -> None:
    annotation = _link_with_color()
    handler = PDLinkAppearanceHandler(annotation, None)
    assert handler.get_annotation() is annotation
    assert handler.get_document() is None
