"""Wave 1396 branch-coverage tests for ``Type1CharString.handle_type1_command``.

Each operator arm in ``handle_type1_command`` guards itself with an
``if len(n) >= N:`` (or ``if n:``) check; the False branch is the
"insufficient operands" fall-through to the final ``n.clear()`` on line
521. The arms themselves are exercised by the existing coverage tests;
these tests drive each arm with too-few operands to close the False
branches reported at 451->521, 457->521, ..., 508->521.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.type1_char_string import (
    Type1CharString,
    _RenderContext,
)


@pytest.fixture
def cs() -> Type1CharString:
    return Type1CharString(
        font=None, font_name="Test", glyph_name="glyph", sequence=[],
    )


@pytest.fixture
def ctx() -> _RenderContext:
    return _RenderContext()


@pytest.mark.parametrize(
    ("op", "args"),
    [
        ("rmoveto", []),       # needs 2
        ("rmoveto", [1.0]),    # needs 2
        ("vmoveto", []),       # needs 1
        ("hmoveto", []),       # needs 1
        ("rlineto", []),       # needs 2
        ("rlineto", [3.0]),    # needs 2
        ("hlineto", []),       # needs 1
        ("vlineto", []),       # needs 1
        ("rrcurveto", []),     # needs 6
        ("rrcurveto", [1.0, 2.0, 3.0, 4.0, 5.0]),  # needs 6
        ("sbw", []),           # needs 3
        ("sbw", [1.0, 2.0]),   # needs 3
        ("hsbw", []),          # needs 2
        ("hsbw", [1.0]),       # needs 2
        ("vhcurveto", []),     # needs 4
        ("vhcurveto", [1.0, 2.0, 3.0]),  # needs 4
        ("hvcurveto", []),     # needs 4
        ("hvcurveto", [1.0, 2.0, 3.0]),  # needs 4
        ("seac", []),          # needs 5
        ("seac", [1.0, 2.0, 3.0, 4.0]),  # needs 5
        ("setcurrentpoint", []),  # needs 2
        ("setcurrentpoint", [1.0]),  # needs 2
        ("callothersubr", []),  # needs 1
        ("div", []),           # needs 2
        ("div", [4.0]),        # needs 2
    ],
)
def test_handle_type1_command_insufficient_operands_clears_stack(
    cs: Type1CharString,
    ctx: _RenderContext,
    op: str,
    args: list,
) -> None:
    """Insufficient operands must short-circuit the operator and clear ``n``.

    Closes the False-branch arrows 451->521, 457->521, 463->521, 469->521,
    472->521, 475->521, 478->521, 483->521, 488->521, 493->521, 496->521,
    499->521, 502->521, 505->521, 508->521 in pypdfbox/fontbox/cff/
    type1_char_string.py.
    """
    numbers = list(args)
    initial_path = list(ctx.path)
    initial_width = ctx.width
    initial_lsb = ctx.left_side_bearing
    initial_flex_points = list(ctx.flex_points)

    cs.handle_type1_command(ctx, numbers, op)

    # The operator-arm body never ran, so observable state must be
    # unchanged. The final n.clear() at line 521 runs regardless.
    assert numbers == []
    assert ctx.path == initial_path
    assert ctx.width == initial_width
    assert ctx.left_side_bearing == initial_lsb
    assert ctx.flex_points == initial_flex_points
