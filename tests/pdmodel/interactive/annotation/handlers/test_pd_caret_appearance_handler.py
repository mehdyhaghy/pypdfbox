"""Tests for :class:`PDCaretAppearanceHandler` — the caret glyph is a
filled symmetric Bezier ``tooth``.
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.annotation.handlers.pd_caret_appearance_handler import (
    PDCaretAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_caret import (
    PDAnnotationCaret,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_caret_handler_subclasses_abstract_base() -> None:
    from pypdfbox.pdmodel.interactive.annotation.handlers.pd_abstract_appearance_handler import (
        PDAbstractAppearanceHandler,
    )

    handler = PDCaretAppearanceHandler(PDAnnotationCaret())
    assert isinstance(handler, PDAbstractAppearanceHandler)


def test_caret_handler_constructor_keeps_annotation() -> None:
    annotation = PDAnnotationCaret()
    handler = PDCaretAppearanceHandler(annotation)
    assert handler.get_annotation() is annotation


def test_caret_handler_generate_normal_appearance_no_rect() -> None:
    annotation = PDAnnotationCaret()
    handler = PDCaretAppearanceHandler(annotation)
    # No /Rect — must be a clean no-op.
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_caret_handler_generate_normal_appearance_writes_stream() -> None:
    annotation = PDAnnotationCaret()
    annotation.set_rectangle(PDRectangle(0.0, 0.0, 20.0, 20.0))
    annotation.set_color([1.0, 0.0, 0.0])
    handler = PDCaretAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    entry = ap.get_normal_appearance()
    assert entry is not None and entry.is_stream()


def test_caret_handler_generate_normal_appearance_ignores_wrong_type() -> None:
    handler = PDCaretAppearanceHandler(PDAnnotation())
    handler.generate_normal_appearance()  # must not raise


def test_caret_handler_rollover_and_down_are_noops() -> None:
    handler = PDCaretAppearanceHandler(PDAnnotationCaret())
    assert handler.generate_rollover_appearance() is None
    assert handler.generate_down_appearance() is None
