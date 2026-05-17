"""Coverage-boost tests for the text-annotation appearance handler.

Targets ``pypdfbox.pdmodel.interactive.annotation.handlers.pd_text_appearance_handler``:
the public ``draw_*`` snake_case aliases (one-liners delegating to the
private ``_draw_*`` painters) and the unsupported-name early-out branches
that the existing wave-1280/1285 smoke tests don't reach.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.annotation.handlers.pd_text_appearance_handler import (
    PDTextAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
    PDAnnotationText,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (0.0, 0.0, 100.0, 100.0)


def _text(name: str) -> PDAnnotationText:
    annotation = PDAnnotationText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 1.0])
    annotation.set_name(name)
    return annotation


def test_generate_normal_appearance_unsupported_name_short_circuits() -> None:
    """Line 113: a ``/Name`` that isn't in ``_SUPPORTED_NAMES`` returns
    without emitting any appearance stream."""
    annotation = _text("Bogus")
    handler = PDTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    # Either the appearance dictionary wasn't created at all, or it was
    # created but no /N stream was written.
    ap = annotation.get_appearance_dictionary()
    if ap is not None:
        assert ap.get_normal_appearance() is None


def test_generate_normal_appearance_rejects_non_text_annotation() -> None:
    """Line 111: an annotation that isn't a ``PDAnnotationText`` returns
    immediately. Use a Link annotation which has a /Rect."""
    annotation = PDAnnotationLink()
    annotation.set_rectangle(PDRectangle(*_RECT))
    handler = PDTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    # No appearance stream should have been generated.
    ap = annotation.get_appearance_dictionary()
    if ap is not None:
        assert ap.get_normal_appearance() is None


@pytest.mark.parametrize(
    "name",
    [
        PDAnnotationText.NAME_NOTE,
        PDAnnotationText.NAME_CROSS,
        PDAnnotationText.NAME_CIRCLE,
        PDAnnotationText.NAME_INSERT,
        PDAnnotationText.NAME_HELP,
        PDAnnotationText.NAME_PARAGRAPH,
        PDAnnotationText.NAME_NEW_PARAGRAPH,
        PDAnnotationText.NAME_STAR,
        PDAnnotationText.NAME_CHECK,
        PDAnnotationText.NAME_RIGHT_ARROW,
        PDAnnotationText.NAME_RIGHT_POINTER,
        PDAnnotationText.NAME_CROSS_HAIRS,
        PDAnnotationText.NAME_UP_ARROW,
        PDAnnotationText.NAME_UP_LEFT_ARROW,
        PDAnnotationText.NAME_COMMENT,
        PDAnnotationText.NAME_KEY,
    ],
)
def test_generate_normal_appearance_dispatches_every_painter(name: str) -> None:
    """Walk every ``/Name`` in the dispatch table — each painter draws
    its glyph and writes an appearance stream."""
    annotation = _text(name)
    handler = PDTextAppearanceHandler(annotation)
    handler.generate_normal_appearance()
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    assert ap.get_normal_appearance() is not None


# ----------------------------------------------------------------------
# Public ``draw_*`` aliases (one-line forwarders) — lines 223, 230, 237,
# 244, 251, 258, 265, 272, 279, 286, 293, 300, 312, 184
# ----------------------------------------------------------------------


def _setup_for_painter(name: str) -> tuple[
    PDAnnotationText, PDTextAppearanceHandler
]:
    annotation = _text(name)
    handler = PDTextAppearanceHandler(annotation)
    return annotation, handler


def test_draw_note_alias_delegates_to_private_helper() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_NOTE)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_note(annotation, cs)


def test_draw_circles_alias() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_CIRCLE)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_circles(annotation, cs)


def test_draw_insert_alias() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_INSERT)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_insert(annotation, cs)


def test_draw_cross_hairs_alias() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_CROSS_HAIRS)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_cross_hairs(annotation, cs)


def test_draw_help_alias() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_HELP)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_help(annotation, cs)


def test_draw_comment_alias() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_COMMENT)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_comment(annotation, cs)


def test_draw_key_alias() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_KEY)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_key(annotation, cs)


def test_draw_paragraph_alias() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_PARAGRAPH)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_paragraph(annotation, cs)


def test_draw_new_paragraph_alias() -> None:
    annotation, handler = _setup_for_painter(
        PDAnnotationText.NAME_NEW_PARAGRAPH
    )
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_new_paragraph(annotation, cs)


def test_draw_right_arrow_alias() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_RIGHT_ARROW)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_right_arrow(annotation, cs)


def test_draw_up_arrow_alias() -> None:
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_UP_ARROW)
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_up_arrow(annotation, cs)


def test_draw_up_left_arrow_alias() -> None:
    annotation, handler = _setup_for_painter(
        PDAnnotationText.NAME_UP_LEFT_ARROW
    )
    with handler.get_normal_appearance_as_content_stream() as cs:
        handler.draw_up_left_arrow(annotation, cs)


def test_draw_zapf_alias() -> None:
    """Line 312: ``draw_zapf`` forwards to ``_draw_zapf``."""
    annotation, handler = _setup_for_painter(PDAnnotationText.NAME_CROSS)
    with handler.get_normal_appearance_as_content_stream() as cs:
        # Pass a known glyph name from ZapfDingbats; arbitrary baseline /
        # translate-y values.
        handler.draw_zapf(annotation, cs, 0.0, 0.0, "a1")


def test_adjust_rect_and_b_box_public_alias() -> None:
    """Line 184: ``adjust_rect_and_b_box`` forwards to
    ``_adjust_rect_and_bbox`` (the camelCase-stripped public mirror)."""
    annotation = _text(PDAnnotationText.NAME_NOTE)
    handler = PDTextAppearanceHandler(annotation)
    bbox = handler.adjust_rect_and_b_box(annotation, 18.0, 20.0)
    assert bbox.get_width() == 18.0
    assert bbox.get_height() == 20.0
