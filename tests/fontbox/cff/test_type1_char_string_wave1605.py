"""PDFBOX-6267 — ``rmoveto`` uses the *last* two operands.

Upstream (3.0 branch, r1938289) changed the non-flex ``RMOVETO`` arm of
``Type1CharString.handleType1Command`` from ``numbers.get(0)/get(1)`` to
``numbers.get(size - 2)/get(size - 1)``. Some fonts in the wild leave
stale operands on the stack in front of the two that belong to the
operator (see the referenced pdf.js issue 10175); Type 1 interpreters
read the topmost pair, so the leading junk has to be ignored.

Upstream shipped no JUnit test with that commit; these are hand-written.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.type1_char_string import (
    Type1CharString,
    _RenderContext,
)


def _char_string() -> Type1CharString:
    return Type1CharString(
        font=None, font_name="Test", glyph_name="glyph", sequence=[]
    )


def test_rmoveto_with_exactly_two_operands_is_unchanged() -> None:
    ctx = _RenderContext()
    _char_string().handle_type1_command(ctx, [10.0, 20.0], "rmoveto")

    assert ctx.path == [("moveto", 10.0, 20.0)]
    assert ctx.current == (10.0, 20.0)


def test_rmoveto_with_extra_leading_operands_uses_the_last_two() -> None:
    ctx = _RenderContext()
    # 100/200 are stale stack residue; 10/20 are the operator's own pair.
    _char_string().handle_type1_command(ctx, [100.0, 200.0, 10.0, 20.0], "rmoveto")

    assert ctx.path == [("moveto", 10.0, 20.0)]
    assert ctx.current == (10.0, 20.0)


def test_rmoveto_is_relative_to_the_current_point() -> None:
    ctx = _RenderContext()
    cs = _char_string()
    cs.handle_type1_command(ctx, [5.0, 5.0], "rmoveto")
    cs.handle_type1_command(ctx, [999.0, 1.0, 2.0], "rmoveto")

    assert ctx.path == [("moveto", 5.0, 5.0), ("moveto", 6.0, 7.0)]
    assert ctx.current == (6.0, 7.0)


def test_flex_rmoveto_still_collects_the_first_two_operands() -> None:
    """Upstream left the flex arm alone — only the non-flex branch takes the
    last two numbers."""
    ctx = _RenderContext()
    ctx.is_flex = True
    _char_string().handle_type1_command(ctx, [100.0, 200.0, 10.0, 20.0], "rmoveto")

    assert ctx.flex_points == [(100.0, 200.0)]
    assert ctx.path == []
