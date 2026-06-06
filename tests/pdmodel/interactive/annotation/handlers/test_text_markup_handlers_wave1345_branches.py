"""Wave 1345 coverage-boost — exercise the cold early-return + dash-array
branches of the four text-markup appearance handlers (Highlight,
Strikeout, Underline, Squiggly).

Pre-wave 1345 the existing happy-path smoke tests at
``test_pd_appearance_handlers_wave1280.py`` and
``test_pd_appearance_handlers_wave1285.py`` left these arms uncovered:

* wrong-annotation-type guard
* missing /Rect early return
* missing /QuadPoints early return
* missing /C (color) early return
* /Border width = 0 -> _ADOBE_DEFAULT_WIDTH fallback
* /BS STYLE_DASHED -> ``set_dash_pattern`` emission
* highlight vertical-quad rounded-corner branch + diagonal fallback
* squiggly zero-length quad ``continue``
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat
from pypdfbox.pdmodel.interactive.annotation.handlers import (
    PDHighlightAppearanceHandler,
    PDSquigglyAppearanceHandler,
    PDStrikeoutAppearanceHandler,
    PDUnderlineAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_highlight import (
    PDAnnotationHighlight,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_squiggly import (
    PDAnnotationSquiggly,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_strikeout import (
    PDAnnotationStrikeout,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_underline import (
    PDAnnotationUnderline,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (0.0, 0.0, 100.0, 50.0)
_QUAD = [0.0, 0.0, 100.0, 0.0, 100.0, 20.0, 0.0, 20.0]


def _appearance_bytes(annotation) -> bytes:
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    stream = ap.get_normal_appearance().get_appearance_stream()
    return stream.get_stream().to_byte_array()


def _zero_width_border() -> COSArray:
    """``/Border [0 0 0]`` — explicit width=0 to trigger the
    ``_ADOBE_DEFAULT_WIDTH`` fallback inside the handlers."""
    arr = COSArray()
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(0.0))
    return arr


def _dashed_border_style() -> PDBorderStyleDictionary:
    bs = PDBorderStyleDictionary()
    bs.set_width(2.0)
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    bs.set_dash_style([3.0])
    return bs


# ---------------------------------------------------------------------------
# wrong-annotation-type guard (all four)
# ---------------------------------------------------------------------------


def test_highlight_handler_wrong_subtype_is_noop() -> None:
    PDHighlightAppearanceHandler(PDAnnotation()).generate_normal_appearance()
    # no exception, no appearance dict


def test_strikeout_handler_wrong_subtype_is_noop() -> None:
    PDStrikeoutAppearanceHandler(PDAnnotation()).generate_normal_appearance()


def test_underline_handler_wrong_subtype_is_noop() -> None:
    PDUnderlineAppearanceHandler(PDAnnotation()).generate_normal_appearance()


def test_squiggly_handler_wrong_subtype_is_noop() -> None:
    PDSquigglyAppearanceHandler(PDAnnotation()).generate_normal_appearance()


# ---------------------------------------------------------------------------
# missing /QuadPoints
# ---------------------------------------------------------------------------


def test_highlight_handler_no_quadpoints_is_noop() -> None:
    annotation = PDAnnotationHighlight()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 1.0, 0.0])
    annotation.set_quad_points(None)  # clear default empty array
    PDHighlightAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_strikeout_handler_no_quadpoints_is_noop() -> None:
    annotation = PDAnnotationStrikeout()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(None)
    PDStrikeoutAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_underline_handler_no_quadpoints_is_noop() -> None:
    annotation = PDAnnotationUnderline()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(None)
    PDUnderlineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_squiggly_handler_no_quadpoints_is_noop() -> None:
    annotation = PDAnnotationSquiggly()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(None)
    PDSquigglyAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ---------------------------------------------------------------------------
# missing /Rect
# ---------------------------------------------------------------------------


def test_strikeout_handler_no_rect_is_noop() -> None:
    annotation = PDAnnotationStrikeout()
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(_QUAD)
    PDStrikeoutAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_underline_handler_no_rect_is_noop() -> None:
    annotation = PDAnnotationUnderline()
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(_QUAD)
    PDUnderlineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_squiggly_handler_no_rect_is_noop() -> None:
    annotation = PDAnnotationSquiggly()
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(_QUAD)
    PDSquigglyAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_highlight_handler_no_rect_is_noop() -> None:
    annotation = PDAnnotationHighlight()
    annotation.set_color([1.0, 1.0, 0.0])
    annotation.set_quad_points(_QUAD)
    PDHighlightAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ---------------------------------------------------------------------------
# missing /C color
# ---------------------------------------------------------------------------


def test_highlight_handler_no_color_is_noop() -> None:
    annotation = PDAnnotationHighlight()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_quad_points(_QUAD)
    PDHighlightAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_strikeout_handler_no_color_is_noop() -> None:
    annotation = PDAnnotationStrikeout()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_quad_points(_QUAD)
    PDStrikeoutAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_underline_handler_no_color_is_noop() -> None:
    annotation = PDAnnotationUnderline()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_quad_points(_QUAD)
    PDUnderlineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_squiggly_handler_no_color_is_noop() -> None:
    annotation = PDAnnotationSquiggly()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_quad_points(_QUAD)
    PDSquigglyAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ---------------------------------------------------------------------------
# /Border width = 0  -> _ADOBE_DEFAULT_WIDTH fallback
# (strikeout / underline / squiggly only — highlight uses ab.width without
# the 0 -> default fallback.)
# ---------------------------------------------------------------------------


def test_strikeout_handler_zero_width_border_uses_default() -> None:
    annotation = PDAnnotationStrikeout()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(_QUAD)
    annotation.set_border(_zero_width_border())
    PDStrikeoutAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # 1.5-pt line width should appear in the content stream as "1.5 w".
    assert b"1.5 w" in body


def test_underline_handler_zero_width_border_uses_default() -> None:
    annotation = PDAnnotationUnderline()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(_QUAD)
    annotation.set_border(_zero_width_border())
    PDUnderlineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"1.5 w" in body


def test_squiggly_handler_zero_width_border_uses_default() -> None:
    annotation = PDAnnotationSquiggly()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(_QUAD)
    annotation.set_border(_zero_width_border())
    PDSquigglyAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Upstream's squiggly handler ignores the line width in the outer stream
    # (PDSquigglyAppearanceHandler.java:112 "we ignore dash pattern and line
    # width for now"): the zig-zag is painted from a tiling pattern in a form
    # XObject, so no "1.5 w" is emitted. The default-1.5 width is still applied
    # to the /Rect padding. Verify the form XObject path was taken instead.
    assert b"1.5 w" not in body
    assert b"cm" in body and b"Do" in body


# ---------------------------------------------------------------------------
# Dashed /BS  -> set_dash_pattern emission
# (strikeout + underline only — squiggly does not emit dash_array;
# its content-stream path skips the dash array branch.)
# ---------------------------------------------------------------------------


def test_strikeout_handler_emits_dash_pattern_for_dashed_border() -> None:
    annotation = PDAnnotationStrikeout()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(_QUAD)
    annotation.set_border_style(_dashed_border_style())
    PDStrikeoutAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # "d" is the PDF "set dash pattern" operator.
    assert b" d" in body


def test_underline_handler_emits_dash_pattern_for_dashed_border() -> None:
    annotation = PDAnnotationUnderline()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    annotation.set_quad_points(_QUAD)
    annotation.set_border_style(_dashed_border_style())
    PDUnderlineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b" d" in body


# ---------------------------------------------------------------------------
# Squiggly zero-length quad continue
# ---------------------------------------------------------------------------


def test_squiggly_handler_skips_zero_length_quad() -> None:
    """A quad whose lower edge has length zero must be skipped (the
    ``length == 0: continue`` branch)."""
    annotation = PDAnnotationSquiggly()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    # Indices 4 == 6 and 5 == 7 -> degenerate bottom edge of length 0.
    annotation.set_quad_points([10.0, 10.0, 10.0, 0.0, 10.0, 0.0, 10.0, 0.0])
    PDSquigglyAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # No path operators were emitted from the degenerate quad — body holds
    # just the opacity / colour / line-width prologue. Tokenise so the colour
    # operator (``... SC``) isn't mistaken for the stroke operator ``S``.
    tokens = body.split()
    assert b"S" not in tokens  # stroke
    assert b"l" not in tokens  # line_to


# ---------------------------------------------------------------------------
# Highlight rounded-corner branches
# ---------------------------------------------------------------------------


def test_highlight_handler_vertical_quad_emits_curves() -> None:
    """Vertical-orientation quad: y1==y5, x0==x2, y3==y7, x4==x6 — hits
    line 111 (vertical-highlight delta) plus the line 124 branch
    (``paths_array[offset + 5] == paths_array[offset + 1]`` mid-curve)."""
    annotation = PDAnnotationHighlight()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 50.0, 200.0))
    annotation.set_color([1.0, 1.0, 0.0])
    # (x0,y0)=(0,100), (x1,y1)=(0,0), (x2,y2)=(20,100), (x3,y3)=(20,0)
    # Vertical: y1==y5, x0==x2, y3==y7, x4==x6
    annotation.set_quad_points(
        [0.0, 100.0, 0.0, 0.0, 20.0, 100.0, 20.0, 0.0]
    )
    PDHighlightAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"c" in body


def test_highlight_handler_diagonal_quad_uses_lineto_fallback() -> None:
    """Skewed quad — neither horizontal nor vertical branch matches, so
    rounded-corner curves degrade to ``cs.line_to`` (line 133 + 147 in
    the source). Validates that the fall-through path still emits a
    proper closed fill."""
    annotation = PDAnnotationHighlight()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 200.0, 200.0))
    annotation.set_color([1.0, 1.0, 0.0])
    # No pair of coordinates equal => neither horizontal nor vertical
    # branch is taken, delta stays 0, and both curve_to-or-line_to
    # decisions hit the line_to else arm.
    annotation.set_quad_points(
        [10.0, 30.0, 90.0, 25.0, 95.0, 80.0, 15.0, 75.0]
    )
    PDHighlightAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # line_to operator must be present (the fallback branch).
    assert b" l" in body
    # Fill operator emitted at the end of each quad.
    assert b"f" in body
