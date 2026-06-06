"""Tests for the wave-1285 expansion of the text-family appearance
handlers — :class:`PDTextAppearanceHandler`,
:class:`PDFreeTextAppearanceHandler`, :class:`PDCaretAppearanceHandler`,
:class:`PDSoundAppearanceHandler`, :class:`PDSquigglyAppearanceHandler`.

The wave-1280 smoke tests already verified that each handler writes a
non-empty appearance dictionary. These tests dig deeper:

* every supported ``/Name`` value on ``PDAnnotationText`` paints a
  non-empty appearance stream,
* the caret handler grows ``/Rect`` + ``/RD`` when ``/RD`` is missing
  and leaves them alone when ``/RD`` is already set,
* the free-text handler honours ``/DA``-supplied font + non-stroking
  color, the ``/DS`` color override, and a ``/CL`` callout polyline,
* the squiggly handler emits stroked zig-zag polylines per quad,
* the sound handler is a complete no-op (matches upstream).
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.annotation.handlers.pd_caret_appearance_handler import (
    PDCaretAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_free_text_appearance_handler import (
    PDFreeTextAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_sound_appearance_handler import (
    PDSoundAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_squiggly_appearance_handler import (
    PDSquigglyAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_text_appearance_handler import (
    PDTextAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_caret import (
    PDAnnotationCaret,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_sound import (
    PDAnnotationSound,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_squiggly import (
    PDAnnotationSquiggly,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
    PDAnnotationText,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _stream_body(annotation: object) -> bytes:
    ap = annotation.get_appearance_dictionary()  # type: ignore[attr-defined]
    assert ap is not None
    entry = ap.get_normal_appearance()
    assert entry is not None
    return entry.get_appearance_stream().get_cos_object().to_byte_array()


# ----------------------------------------------------------------------
# PDTextAppearanceHandler — all 16 supported /Name values write a stream
# ----------------------------------------------------------------------


_TEXT_RECTS: dict[str, tuple[float, float]] = {
    PDAnnotationText.NAME_NOTE: (18.0, 20.0),
    PDAnnotationText.NAME_CROSS: (20.0, 20.0),
    PDAnnotationText.NAME_CIRCLE: (20.0, 20.0),
    PDAnnotationText.NAME_INSERT: (17.0, 20.0),
    PDAnnotationText.NAME_HELP: (20.0, 20.0),
    PDAnnotationText.NAME_PARAGRAPH: (20.0, 20.0),
    PDAnnotationText.NAME_NEW_PARAGRAPH: (13.0, 20.0),
    PDAnnotationText.NAME_STAR: (20.0, 20.0),
    PDAnnotationText.NAME_CHECK: (20.0, 20.0),
    PDAnnotationText.NAME_RIGHT_ARROW: (20.0, 20.0),
    PDAnnotationText.NAME_RIGHT_POINTER: (20.0, 20.0),
    PDAnnotationText.NAME_CROSS_HAIRS: (20.0, 20.0),
    PDAnnotationText.NAME_UP_ARROW: (17.0, 20.0),
    PDAnnotationText.NAME_UP_LEFT_ARROW: (17.0, 17.0),
    PDAnnotationText.NAME_COMMENT: (18.0, 18.0),
    PDAnnotationText.NAME_KEY: (13.0, 18.0),
}


@pytest.mark.parametrize("name", sorted(_TEXT_RECTS.keys()))
def test_text_handler_every_supported_name_paints_stream(name: str) -> None:
    width, height = _TEXT_RECTS[name]
    annotation = PDAnnotationText()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, width, height))
    annotation.set_color([1.0, 1.0, 0.0])
    annotation.set_name(name)
    handler = PDTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    body = _stream_body(annotation)
    assert body, f"appearance stream is empty for /Name = {name}"


def test_text_handler_zapf_helper_routes_to_glyph_drawers() -> None:
    """The four /Name values that dispatch through drawZapf (Cross,
    Star, Check, RightPointer) all produce non-empty streams that
    exercise the hand-built glyph approximations."""
    for name in (
        PDAnnotationText.NAME_CROSS,
        PDAnnotationText.NAME_STAR,
        PDAnnotationText.NAME_CHECK,
        PDAnnotationText.NAME_RIGHT_POINTER,
    ):
        annotation = PDAnnotationText()
        annotation.set_rectangle(PDRectangle(0.0, 0.0, 20.0, 20.0))
        annotation.set_name(name)
        handler = PDTextAppearanceHandler(annotation)
        handler.generate_normal_appearance()
        body = _stream_body(annotation)
        assert b"m" in body, f"missing moveTo op for {name}"


def test_text_handler_add_path_dispatches_operators() -> None:
    """``add_path`` should translate the synthetic ``(op, coords)``
    tuples into the corresponding content-stream operators."""
    annotation = PDAnnotationText()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 18.0, 20.0))
    annotation.set_name(PDAnnotationText.NAME_NOTE)
    handler = PDTextAppearanceHandler(annotation)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.add_path(
            cs,
            [
                ("M", (0.0, 0.0)),
                ("L", (10.0, 0.0)),
                ("C", (10.0, 5.0, 5.0, 10.0, 0.0, 10.0)),
                ("H", ()),
            ],
        )
        cs.stroke()
    body = _stream_body(annotation)
    assert b"m" in body
    assert b"l" in body
    assert b"c" in body
    assert b"h" in body


def test_text_handler_note_emits_lines() -> None:
    """The Note glyph should emit four horizontal rule lines on top of
    the outer rectangle — a parseable proof of full path generation."""
    annotation = PDAnnotationText()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 18.0, 20.0))
    annotation.set_name(PDAnnotationText.NAME_NOTE)
    handler = PDTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    body = _stream_body(annotation)
    # Body should have at least 4 move + 4 line ops for the rules plus
    # the rectangle. We don't assert exact counts because indentation
    # and decimals may interleave; just sanity-check non-emptiness.
    assert body.count(b" m\n") >= 4 or body.count(b" m ") >= 4


def test_text_handler_comment_emits_curves() -> None:
    """The Comment glyph uses Bezier curves for the speech bubble."""
    annotation = PDAnnotationText()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 18.0, 18.0))
    annotation.set_name(PDAnnotationText.NAME_COMMENT)
    handler = PDTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    body = _stream_body(annotation)
    assert b"c" in body  # cubic Bezier op present


# ----------------------------------------------------------------------
# PDCaretAppearanceHandler — /RD + /Rect handling
# ----------------------------------------------------------------------


def test_caret_handler_grows_rect_and_sets_rd_when_missing() -> None:
    annotation = PDAnnotationCaret()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 50.0, 100.0))
    handler = PDCaretAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    # /RD now exists.
    rd = annotation.get_rect_differences()
    assert rd is not None and len(rd) == 4
    # rd value = min(height/10, 5) — here 100/10 = 10, capped to 5.
    assert rd == [5.0, 5.0, 5.0, 5.0]
    # /Rect grew by 5 on every side: (-5, -5, 55, 105).
    rect = annotation.get_rectangle()
    assert rect.get_lower_left_x() == -5.0
    assert rect.get_lower_left_y() == -5.0
    assert rect.get_upper_right_x() == 55.0
    assert rect.get_upper_right_y() == 105.0


def test_caret_handler_respects_preset_rd() -> None:
    annotation = PDAnnotationCaret()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 50.0, 50.0))
    annotation.set_rect_differences([1.0, 2.0, 3.0, 4.0])
    handler = PDCaretAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    # /RD must remain untouched.
    assert annotation.get_rect_differences() == [1.0, 2.0, 3.0, 4.0]


def test_caret_handler_rd_capped_at_5() -> None:
    """``rd = min(height / 10, 5)``. With height 30 the cap kicks in at 3."""
    annotation = PDAnnotationCaret()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 30.0, 30.0))
    handler = PDCaretAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    rd = annotation.get_rect_differences()
    assert rd == [3.0, 3.0, 3.0, 3.0]


# ----------------------------------------------------------------------
# PDFreeTextAppearanceHandler — /DA, /DS, /CL paths
# ----------------------------------------------------------------------


def test_free_text_handler_parses_da_font_and_color() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 200.0, 100.0))
    annotation.set_default_appearance("/Helv 14 Tf 0.5 0.25 0.75 rg")
    annotation.set_contents("Hello world")
    handler = PDFreeTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    # The handler must extract font size 14.
    assert handler._font_size == 14.0
    components = handler.extract_non_stroking_color(annotation)
    assert components == [0.5, 0.25, 0.75]
    # Stream body must contain a Tj for the contents.
    body = _stream_body(annotation)
    assert b"Tj" in body


def test_free_text_handler_default_da_returns_black() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 50.0))
    # No /DA at all → DeviceGray 0 (black).
    handler = PDFreeTextAppearanceHandler(annotation)
    assert handler.extract_non_stroking_color(annotation) == [0.0]


def test_free_text_handler_callout_path_drawn() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(50.0, 50.0, 150.0, 100.0))
    annotation.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    annotation.set_callout([10.0, 10.0, 30.0, 30.0, 50.0, 50.0])
    annotation.set_contents("see this")
    handler = PDFreeTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    body = _stream_body(annotation)
    # Callout polyline writes m + l + S.
    assert b"m" in body
    assert b"l" in body


def test_free_text_handler_handles_empty_contents() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 50.0))
    handler = PDFreeTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()  # must not raise
    assert annotation.get_appearance_dictionary() is not None


def test_free_text_handler_grows_rect_with_callout() -> None:
    """When a callout is present, the /Rect must grow to enclose the
    callout polyline plus ten times the border width as a safety
    margin."""
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(50.0, 50.0, 150.0, 100.0))
    annotation.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    # Callout endpoint at (5, 5) is well outside the initial rectangle.
    annotation.set_callout([5.0, 5.0, 30.0, 30.0, 50.0, 50.0])
    handler = PDFreeTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    rect = annotation.get_rectangle()
    # Lower-left must now be <= (5, 5) minus border padding.
    assert rect.get_lower_left_x() <= 5.0
    assert rect.get_lower_left_y() <= 5.0


# ----------------------------------------------------------------------
# PDSquigglyAppearanceHandler — zig-zag polyline
# ----------------------------------------------------------------------


def test_squiggly_handler_paints_zigzag_per_quad() -> None:
    annotation = PDAnnotationSquiggly()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 20.0))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points([0.0, 20.0, 100.0, 20.0, 100.0, 0.0, 0.0, 0.0])
    handler = PDSquigglyAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    body = _stream_body(annotation)
    # The zig-zag is now painted from a tiling pattern wrapped in a form
    # XObject (faithful upstream port): the outer stream sets the colour and
    # draws the form (cm + Do), matching PDFBox.
    assert b"cm" in body
    assert b"Do" in body
    # The zig-zag tooth itself lives in the pattern cell content stream
    # (0 1 m 5 11 l 10 1 l S) — registered under the form's /Resources/Pattern.
    ap = annotation.get_appearance_dictionary().get_normal_appearance()
    form_stream = ap.get_appearance_stream()
    xobjects = form_stream.get_resources().get_cos_object().get_dictionary_object(
        "XObject"
    )
    assert xobjects is not None, "squiggly outer stream did not register a form"
    form_cos = next(iter(xobjects.values()))
    if hasattr(form_cos, "get_object"):
        form_cos = form_cos.get_object()
    pattern_dict = form_cos.get_dictionary_object("Resources").get_dictionary_object(
        "Pattern"
    )
    assert pattern_dict is not None, "form did not register a tiling pattern"
    pattern_cos = next(iter(pattern_dict.values()))
    if hasattr(pattern_cos, "get_object"):
        pattern_cos = pattern_cos.get_object()
    cell = pattern_cos.create_input_stream().read()
    assert b"m" in cell and b"l" in cell and b"S" in cell, (
        f"tiling-pattern cell did not stroke the zig-zag tooth: {cell!r}"
    )


def test_squiggly_handler_no_color_is_silent_noop() -> None:
    annotation = PDAnnotationSquiggly()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 100.0, 20.0))
    annotation.set_quad_points([0.0, 20.0, 100.0, 20.0, 100.0, 0.0, 0.0, 0.0])
    handler = PDSquigglyAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    # No color → no stream.
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# PDSoundAppearanceHandler — verifies upstream parity (full no-op)
# ----------------------------------------------------------------------


def test_sound_handler_all_methods_are_noops() -> None:
    annotation = PDAnnotationSound()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 10.0, 10.0))
    annotation.set_color([0.0, 1.0, 0.0])
    handler = PDSoundAppearanceHandler(annotation)
    assert handler.generate_normal_appearance() is None
    assert handler.generate_rollover_appearance() is None
    assert handler.generate_down_appearance() is None
    # And no appearance was written either.
    assert annotation.get_appearance_dictionary() is None
