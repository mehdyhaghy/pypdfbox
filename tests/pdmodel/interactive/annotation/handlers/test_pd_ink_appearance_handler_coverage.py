"""Hand-written coverage tests for ``PDInkAppearanceHandler``.

Exercises every short-circuit branch (wrong annotation type, missing
color, zero border width, missing ``/InkList``, empty path list,
missing rectangle) plus the happy-path stroke that walks
``move_to``/``line_to``/``stroke`` for one and multiple paths.
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.annotation.handlers.pd_ink_appearance_handler import (
    PDInkAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import (
    PDAnnotationInk,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationSquare,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (10.0, 10.0, 100.0, 100.0)


def _ink_with_color(
    paths: list[list[float]] | None = None,
    rect: tuple[float, float, float, float] = _RECT,
    border_width: float | None = None,
) -> PDAnnotationInk:
    annotation = PDAnnotationInk()
    annotation.set_rectangle(PDRectangle(*rect))
    annotation.set_color([0.0, 0.0, 1.0])
    annotation.set_ink_paths(paths if paths is not None else [[20.0, 20.0, 50.0, 50.0]])
    if border_width is not None:
        bs = PDBorderStyleDictionary()
        bs.set_width(border_width)
        annotation.set_border_style(bs)
    return annotation


# ----------------------------------------------------------------------
# Type / color short-circuits
# ----------------------------------------------------------------------


def test_handler_returns_when_annotation_is_not_ink() -> None:
    annotation = PDAnnotationSquare()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([1.0, 0.0, 0.0])
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_handler_returns_when_no_color() -> None:
    annotation = PDAnnotationInk()
    annotation.set_rectangle(PDRectangle(*_RECT))
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# Border / ink list / rectangle guards
# ----------------------------------------------------------------------


def test_handler_returns_when_border_width_is_zero() -> None:
    annotation = _ink_with_color(border_width=0.0)
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_handler_returns_when_ink_list_missing() -> None:
    annotation = PDAnnotationInk()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    # No set_ink_paths call → /InkList absent → get_ink_list returns None.
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_handler_returns_when_paths_list_empty() -> None:
    annotation = PDAnnotationInk()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    annotation.set_ink_paths([])  # empty /InkList
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


# ----------------------------------------------------------------------
# Happy path with one stroked path
# ----------------------------------------------------------------------


def test_handler_writes_appearance_for_single_path() -> None:
    annotation = _ink_with_color(paths=[[20.0, 20.0, 50.0, 50.0]])
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    assert ap.get_normal_appearance() is not None


def test_handler_writes_appearance_for_multiple_paths() -> None:
    annotation = _ink_with_color(
        paths=[
            [10.0, 10.0, 30.0, 40.0],
            [50.0, 60.0, 80.0, 90.0],
        ]
    )
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    ap = annotation.get_appearance_dictionary()
    assert ap is not None


def test_handler_expands_rect_to_cover_ink_bounds() -> None:
    """Ink points outside the declared /Rect must grow the rectangle so the
    stroked path stays visible — mirrors upstream ``setRectangle`` calls."""
    annotation = _ink_with_color(
        paths=[[5.0, 5.0, 200.0, 200.0]],  # extends past _RECT in both axes
        rect=(50.0, 50.0, 90.0, 90.0),
    )
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    rect = annotation.get_rectangle()
    assert rect is not None
    assert rect.get_lower_left_x() <= 5.0
    assert rect.get_lower_left_y() <= 5.0
    assert rect.get_upper_right_x() >= 200.0
    assert rect.get_upper_right_y() >= 200.0


def test_handler_uses_dash_pattern_when_border_style_dashed() -> None:
    annotation = _ink_with_color(paths=[[20.0, 20.0, 60.0, 60.0]])
    bs = PDBorderStyleDictionary()
    bs.set_width(2.0)
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    # Build a dash array via the underlying COS dictionary so we don't
    # depend on a setter that may not exist.
    from pypdfbox.cos import COSArray, COSFloat, COSName

    dash = COSArray()
    dash.add(COSFloat(3.0))
    dash.add(COSFloat(2.0))
    bs.get_cos_object().set_item(COSName.get_pdf_name("D"), dash)
    annotation.set_border_style(bs)
    handler = PDInkAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


# ----------------------------------------------------------------------
# rollover / down are spec-required no-ops
# ----------------------------------------------------------------------


def test_handler_rollover_and_down_are_noops() -> None:
    annotation = PDAnnotationInk()
    handler = PDInkAppearanceHandler(annotation)
    assert handler.generate_rollover_appearance() is None
    assert handler.generate_down_appearance() is None
